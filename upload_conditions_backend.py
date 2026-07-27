import time
import openpyxl
import pandas as pd
import os
import google.generativeai as genai
import json
import ast
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from sigft import config
from sigft.core.excel import headers, pmib_codes


# =============================================================================
# CLASSES DE SERVIÇO (BACKEND PURO)
# =============================================================================
class ConditionsProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.cancel_requested = False  # Flag de parada
        if self.api_key:
            genai.configure(api_key=self.api_key, transport='rest')

    def solicitar_parada(self):
        self.cancel_requested = True

    def _limpar_resposta_json(self, texto_bruto):
        if not texto_bruto: return None
        texto = texto_bruto.replace("```json", "").replace("```", "").strip()
        inicio = texto.find('{')
        fim = texto.rfind('}')
        if inicio != -1 and fim != -1:
            texto = texto[inicio: fim + 1]
        return texto

    def carregar_lookup_status(self, caminho_status_pmib):
        sheet_name = 'Lista de Materiais'
        column_to_find = config.COL_CODIGO_PMIB
        try:
            # NOVO: dtype=str força a ler como texto puro, mantendo a precisão exata do Excel
            df = pd.read_excel(caminho_status_pmib, sheet_name=sheet_name, header=None, dtype=str)

            # CP 1.2: busca dinâmica de cabeçalho via core.excel.headers
            # (mesmo alcance do original: até as 10 primeiras linhas; usa
            # `.head(10)` antes de materializar em lista, como o original,
            # para não converter o arquivo inteiro à toa).
            header_row_index = headers.find_header_row(df.head(10).values.tolist(), column_to_find)
            if header_row_index is None:
                return None, "Coluna 'CÓDIGO PMIB' não encontrada."

            new_header = df.iloc[header_row_index]
            df = df[header_row_index+1:]
            df.columns = new_header

            if 'DESCRIÇÃO' not in df.columns:
                return None, "Coluna 'DESCRIÇÃO' não encontrada."
            if 'CONDIÇÕES' not in df.columns:
                df['CONDIÇÕES'] = ""
            else:
                df['CONDIÇÕES'] = df['CONDIÇÕES'].fillna("")

            # --- CORREÇÃO DO CÓDIGO PMIB (Apóstrofos, vírgula decimal e
            # zeros perdidos) --- CP 1.2: delega para a normalização única e
            # canônica (core.excel.pmib_codes.normalize_pmib), que cobre
            # TODOS os casos que este código só tratava parcialmente (só
            # completava zero quando faltava EXATAMENTE 1 dígito, e não
            # tratava vírgula decimal) — ver docs/refatoracao/PENDENCIAS.md.
            df[column_to_find] = df[column_to_find].apply(pmib_codes.normalize_pmib)

            df.set_index(column_to_find, inplace=True)
            return df, f"Carregado: {len(df)} registros."
        except Exception as e:
            return None, str(e)

    def extrair_dados_brutos_excel(self, caminho_planilha):
        try:
            wb = openpyxl.load_workbook(caminho_planilha, data_only=True)
            if "Ficha Técnica Padrão" not in wb.sheetnames:
                wb.close()
                return None
            ws = wb["Ficha Técnica Padrão"]
        except Exception:
            return None

        def get_val(ref):
            v = ws[ref].value
            return str(v).strip() if v is not None else ""

        dados = {}
        try:
            dados['descricao_breve'] = get_val('H6')
            dados["dimensoes"] = {"comprimento": get_val('H17'), "largura": get_val('H19'), "altura": get_val('H21')}
            dados["peso"] = {"liquido": get_val('P17'), "bruto": get_val('P19')}
            dados['controle_temperatura'] = get_val('M23')

            if get_val('Q21'): dados['sujeito_intemperie'] = "SIM"
            elif get_val('S21'): dados['sujeito_intemperie'] = "NÃO"
            else: dados['sujeito_intemperie'] = ""

            if get_val('G25'): dados['posicao_armazenamento'] = "Vertical"
            elif get_val('G27'): dados['posicao_armazenamento'] = "Horizontal"
            elif get_val('G29'): dados['posicao_armazenamento'] = "Indiferente"
            else: dados['posicao_armazenamento'] = ""

            prot = []
            if get_val('S27'): prot.append("UV")
            if get_val('S29'): prot.append("EL")
            if get_val('S25'): prot.append("SN")
            dados['protecao'] = prot

            if get_val('E33'): dados['nocivo'] = {"status": "Nocivo", "cuidado": get_val('M33')}
            elif get_val('E31'): dados['nocivo'] = {"status": "Não contém", "cuidado": ""}
            else: dados['nocivo'] = {"status": "", "cuidado": ""}

            dados['empilhamento'] = get_val('J35')
            cuid_txt = get_val('J36')
            dados['outros_cuidados'] = {"status": "SIM" if cuid_txt else "NÃO", "cuidados": cuid_txt}

            dados['embalagem_transp'] = get_val('M42')
            dados['posicao_icagem'] = get_val('M45')
            dados['cuidad_preserv'] = get_val('M52')
            dados['limpeza_secagem'] = get_val('M54')
            dados['ferramentas'] = get_val('M56')
            dados['legislacao'] = get_val('M63')
            dados['descarte'] = get_val('M65')

            if get_val('E69'): dados['perigoso_10004'] = "SIM"
            elif get_val('J69'): dados['perigoso_10004'] = "NÃO"
            else: dados['perigoso_10004'] = ""

            log_st = ""
            if get_val('P69'): log_st = "NÃO"
            elif get_val('T69'): log_st = "SIM"
            dados['logistica_reversa'] = {"status": log_st, "logistica_reversa": get_val('N71') if log_st == "SIM" else ""}

            wb.close()
            return dados
        except Exception:
            wb.close()
            return None

    def processar_ia_lote(self, lista_caminhos, df_status, callback_log=None):
        fichas_processadas = []
        # CP 1.2: prefixo de contrato deriva de config.PREFIXO_CONTRATO (era
        # hardcoded "4500063671" aqui); ver
        # core.excel.pmib_codes.extract_contract_pmib_code, usada abaixo.

        system_prompt = """
Você é um assistente especialista em engenharia de materiais e processamento de dados.
Sua tarefa é converter um JSON de "dados brutos" de uma ficha técnica (PMIB) em um JSON "formatado" e limpo.
Responda *apenas* com o JSON formatado.

**REGRAS DE PROCESSAMENTO OBRIGATÓRIAS:**

1.  **Tradução e Limpeza (Regra Mestra):**
    * Qualquer campo de texto livre recebido (ex: 'cuidado', 'embalagem_transp', 'posicao_icagem', etc.) DEVE ser retornado em duas chaves: `_es` (Espanhol) e `_pt` (Português).
    * Se o texto original estiver em Português, traduza para Espanhol.
    * Se o texto original estiver em Espanhol, traduza para Português.
    * Se o texto original estiver em Inglês ou outra língua, traduza para AMBOS (PT e ES).
    * Para os campos a partir de 12, caso o texto esteja em branco, ou como "N/A", complete-o baseado no tipo de equipamento e no intuito do campo.

2.  **'pmib_codigo':** Copie exatamente como veio.

3.  **'dimensoes':**
    * **Validação de Unidade:** Use o 'Descrição do material' (contexto) para avaliar a razoabilidade dos números, tanto do comprimento, quanto da largura e da altura. Se a unidade de entrada não for especificada (ex: 500) e esse valor parecer absurdo em 'cm' (ex: um 'elemento filtrante' com 500 cm de altura, ou 97 cm de comprimento ou largura parece ser muito), **assuma que a entrada estava em milímetros (mm) e converta-a para centímetros.** (ex: Input "500" -> Output "50", "97" -> "9,7").
    * **Validação de Unidade:** Segue a mesma lógica do anterior, mas para casos onde o input esteja muito pequeno, caso a unidade não seja fornecida, avalie se possivelmente a unidade não esteja em metro (ex: um 'elemento filtrate' com 0,5 cm de altura). **assuma que a entrada estava em metros (m) e converta-a para centímetros.** (ex: Input "0.5" ou "0,5"-> Output "50") - faça as mesmas análises para as 3 dimensões.
    * Padronize todos os valores finais para **centímetros (cm)**.
    * Retorne os valores como strings **contendo apenas o número puro**, sem a unidade (ex: "10,5", "50"). Use vírgula como separador decimal
    **Formato do Zero:** Se o valor for menor que 1 (ex: 0.75), **omita o zero à esquerda** (ex: Output ",75").

4.  **'controle_temperatura':**
    * Interprete o texto de entrada (ex: "SIM, manter de 15 a 30 graus") para preencher a estrutura de saída.
    * `necessidade`: Deve ser apenas "SIM" ou "NÃO".
    * `climatizacao`: Se houver dados de temperatura, `ativo`=true. `temp_max`/`temp_min` devem ser em **Graus Celsius (°C)**.
    * `umidade`: Se houver dados de umidade, `ativo`=true. `hr_max`/`hr_min` devem ser em **Porcentagem (%)**.
    * Se `necessidade`="NÃO", `climatizacao.ativo` e `umidade.ativo` devem ser `false` e os valores de temp/umidade devem ser strings vazias.

5.  **'posicao_armazenamento':** Padronize o texto de entrada para "Vertical", "Horizontal", ou "Indiferente".

6.  **'nocivo':**
    * `status`: Interprete o texto de entrada para "Nocivo" ou "Não contém".
    * `cuidado_es` / `cuidado_pt`: Aplique a Regra Mestra de Tradução ao campo 'cuidado' do input.

7.  **'peso':**
    * **Validação de Unidade:** Use o 'Descrição do material' (contexto) para avaliar a razoabilidade. Se um peso de entrada não tiver unidade e parecer absurdo em 'kg' (ex: "Motor Elétrico" com peso "20000"), **assuma que a entrada estava em gramas (g) e converta para kg.** (ex: Input "20000" -> Output "20,0").
    * Padronize todos os valores finais para **quilogramas (kg)**.
    * Retorne como string, usando vírgula como separador decimal.
    * **Formato do Zero:** Se o valor for menor que 1 (ex: 0.26), **omita o zero à esquerda** (ex: Output ",26").

8.  **'sujeito_intemperie':** Padronize para "SIM" ou "NÃO".

9.  **'protecao':** Extraia os códigos ("SN", "UV", "EL") do texto de entrada. Retorne uma lista.

10. **'empilhamento':** Extraia o valor numérico (quantidade) do texto. Retorne como string.

11. **'outros_cuidados':**
    * `status`: Interprete o texto de entrada para "SIM" ou "NÃO".
    * `cuidado_es` / `cuidado_pt`: Aplique a Regra Mestra de Tradução ao campo 'cuidados' do input.

12. **Campos de Texto Único (Transporte, Manutenção, Descarte):**
    * `embalagem_transp` -> `embalagem_transp_es`, `embalagem_transp_pt`
    * `posicao_icagem` -> `posicao_icagem_es`, `posicao_icagem_pt`
    * `cuidad_preserv` -> `cuidad_preserv_es`, `cuidad_preserv_pt`
    * `limpeza_secagem` -> `limpeza_secagem_es`, `limpeza_secagem_pt`
    * `ferramentas` -> `ferramentas_es`, `ferramentas_pt`
    * `legislacao` -> `legislacao_es`, `legislacao_pt`
    * `descarte` -> `descarte_es`, `descarte_pt`
    * **ENRIQUECIMENTO DE TEXTO (Descarte/Legislação):** Se a entrada for genérica (ex: "Seguir legislação local", "Verificar normas", "Conforme lei"), você **NÃO DEVE** apenas traduzir isso. Você deve **SUBSTITUIR** por um texto técnico completo citando as leis aplicáveis (Lei 12.305/2010 Brasil, Lei 3956/09 Paraguai) e a prática correta para aquele tipo de material.

13. **'perigoso_10004':
    * Padronize para "SIM" ou "NÃO".
    * **AUTO-CORREÇÃO:** Use o 'Descrição do material' para validar. Se a entrada for "NÃO", mas o material for intrinsecamente perigoso segundo a NBR 10004 (ex: Óleos, Graxas, Baterias, Tintas, Produtos Químicos, Lixo Eletrônico contaminado), você deve **CORRIGIR para "SIM"**.

14. **'logistica_reversa':**
    * `status`: Interprete para "SIM", "NÃO", ou "Não se aplica".
    * `logistica_reversa_es` / `logistica_reversa_pt`: Aplique a Regra Mestra de Tradução.

---
**15. VALIDAÇÃO DE COERÊNCIA E QUALIDADE (REGRAS AVANÇADAS):**
* Sua principal tarefa é garantir que a ficha final seja COERENTE.
* **Coerência Cruzada:** Use *outros campos* como contexto.
* **EXEMPLO CRÍTICO (Sua Regra):** Se a sua própria saída para `'perigoso_10004'` é `"SIM"`, então a entrada do usuário para `'logistica_reversa'` (ex: "NÃO") ou `'descarte'` (ex: "N/A") está *provavelmente errada*.
* **SUA AÇÃO:** Nestes casos de contradição (Perigoso=SIM mas Logística=NÃO), você **DEVE IGNORAR** a entrada "NÃO" ou "N/A" do usuário. Em vez disso, use seu conhecimento de engenharia sobre o `'Descrição do material'` (ex: DISJUNTOR, BATERIA, ÓLEO) para preencher os campos `descarte_es/pt` e `logistica_reversa_es/pt` com as práticas corretas para um item perigoso daquele tipo. O 'status' de logística reversa deve, então, ser "SIM".
* Se a entrada for "SIM" mas o texto for fraco (ex: "Verificar com fabricante"), substitua-o por uma resposta completa (como no exemplo do Disjuntor).
---

---
**EXEMPLOS DE REGRAS AVANÇADAS (Few-Shot):**
Aqui está um exemplo de como aplicar as regras 12, 13 e 15 (Validação de Qualidade).

**EXEMPLO - INPUT BRUTO (do Excel):**
{
  "pmib_codigo": "4500063671.9999",
  "Descrição do material": "DISJUNTOR TRIPOLAR 250A",
  "legislacao": "N/A",
  "perigoso_10004": "CLASSE 1: PERIGOSO",
  "descarte": "Conforme legislação",
  "logistica_reversa": { "status": "SIM", "logistica_reversa": "Verificar com fabricante."}
}

**EXEMPLO - OUTPUT FORMATADO (JSON Esperado):**
(Note como "N/A" e "Conforme legislação" foram substituídos por respostas completas
baseadas no conhecimento sobre "DISJUNTOR", e "CLASSE 1" virou "SIM")
{
  "pmib_codigo": "4500063671.9999",
  "legislacao_es": "Se aplican las normas NBR IEC 60947-2 y NBR 5410 en Brasil, y normas basadas en la IEC 60947-2 y reglamentos de la ANDE en Paraguay. Las buenas prácticas siguen estándares IEC y recomendaciones de los fabricantes.",
  "legislacao_pt": "Aplicam-se a NBR IEC 60947-2 e NBR 5410 no Brasil, e normas baseadas na IEC 60947-2 e regulamentos da ANDE no Paraguai. As boas práticas seguem os padrões IEC e recomendações dos fabricantes.",
  "perigoso_10004": "SIM",
  "descarte_es": "El disyuntor debe eliminarse como residuo eléctrico/electrónico, según la Ley 12.305/2010 en Brasil y la Ley 3956/09 en Paraguay, priorizando la logística inversa, el reciclaje y la no contaminación ambiental.",
  "descarte_pt": "O disjuntor deve ser descartado como resíduo eletroeletrônico, conforme a Lei 12.305/2010 no Brasil e a Lei 3956/09 no Paraguai, priorizando a logística reversa, reciclagem e não contaminação ambiental.",
  "logistica_reversa": {
    "status": "SIM",
    "logistica_reversa_es": "La logística inversa de disyuntores incluye la recolección, transporte y envío a empresas especializadas, donde se desmontan y sus componentes (metales, plásticos, electrónicos) se reciclan o eliminan según normas ambientales. Puede realizarse mediante acuerdos con fabricantes o puntos autorizados.",
    "logistica_reversa_pt": "A logística reversa de disjuntores envolve a coleta, transporte e envio do material para empresas especializadas, onde é desmontado e seus componentes (metais, plásticos, eletrônicos) são reciclados ou descartados conforme normas ambientais. Pode ser feita por meio de acordos com fabricantes ou pontos de coleta autorizados."
  }

  **CASO 2: NÃO PERIGOSO, MAS COM LOGÍSTICA REVERSA (VÁLVULAS)**
**INPUT:**
{
  "pmib_codigo": "4500063671.2222",
  "Descrição do material": "VÁLVULA DE RETENÇÃO 4 POL",
  "legislacao": "Normas ISO",
  "perigoso_10004": "CLASSE 2: NÃO PERIGOSO",
  "descarte": "Sucata",
  "logistica_reversa": { "status": "NÃO", "logistica_reversa": "N/A"}
}

**OUTPUT:**
{
  "pmib_codigo": "4500063671.2222",
  "legislacao_es": "Se aplican normas internacionales como ISO 5208 (ensayos de fugas en válvulas), ISO 5599 y ASME B16.34. En Brasil, se aplican normas como la NBR 15827 e NBR 12288. En Paraguay, se siguen normativas de la ANDE.",
  "legislacao_pt": "Aplicam-se normas internacionais como ISO 5208 (ensaios de estanqueidade), ISO 5599 e ASME B16.34. No Brasil, destacam-se normas como NBR 15827 e NBR 12288. No Paraguai, seguem-se normas da ANDE.",
  "perigoso_10004": "NÃO",
  "descarte_es": "Las válvulas deben eliminarse como residuos metálicos no peligrosos, si están limpias. Según la Ley 12.305/2010 (Brasil) y Ley 3956/09 (Paraguay), se recomienda su envío a reciclaje. Si están contaminadas, tratamiento especial.",
  "descarte_pt": "Válvulas devem ser descartadas como resíduos metálicos não perigosos, caso estejam limpas. Conforme a Lei 12.305/2010 (Brasil) e Lei 3956/09 (Paraguai), recomenda-se reciclagem. Caso contaminadas, tratamento adequado.",
  "logistica_reversa": {
    "status": "SIM",
    "logistica_reversa_es": "La logística inversa puede incluir la recolección y transporte de válvulas usadas a centros de reciclaje. Si están limpias, se funden como chatarra metálica.",
    "logistica_reversa_pt": "A logística reversa pode incluir coleta e transporte de válvulas usadas para centros de reciclagem. Se estiverem limpas, podem ser fundidas como sucata metálica."
  }
}
--- FIM DO EXEMPLO ---
"""

        safety_settings = {
            'HATE_SPEECH': 'BLOCK_NONE',
            'HARASSMENT': 'BLOCK_NONE',
            'SEXUALLY_EXPLICIT': 'BLOCK_NONE',
            'DANGEROUS': 'BLOCK_NONE'
        }

        for caminho in lista_caminhos:
            if self.cancel_requested:
                if callback_log: callback_log("Processamento de IA interrompido pelo usuário.")
                break  # Sai do loop principal

            nome_arquivo = os.path.basename(caminho)
            pmib_codigo = pmib_codes.extract_contract_pmib_code(caminho)
            if not pmib_codigo:
                if callback_log: callback_log(f"Ignorado (Sem PMIB): {nome_arquivo}")
                continue

            try:
                status_atual = df_status.loc[pmib_codigo, 'CONDIÇÕES']

                # Se houver PMIBs duplicados na planilha, o Pandas retorna uma Series.
                # Seguindo sua regra, pegamos apenas a primeira célula.
                if isinstance(status_atual, pd.Series):
                    status_atual = status_atual.iloc[0]

                if str(status_atual).strip().upper() == "COMPLETO":
                    if callback_log: callback_log(f"PMIB {pmib_codigo} já COMPLETO.")
                    continue
            except KeyError:
                pass

            dados_brutos = self.extrair_dados_brutos_excel(caminho)
            if not dados_brutos: continue

            try:
                descricao = df_status.loc[pmib_codigo, 'DESCRIÇÃO']

                # Mesma proteção contra duplicatas para a descrição não ir "suja" para a IA
                if isinstance(descricao, pd.Series):
                    descricao = descricao.iloc[0]
            except:
                descricao = dados_brutos.get('descricao_breve', 'N/A')

            dados_api_input = {
                "pmib_codigo": pmib_codigo,
                'Descrição do material': descricao,
                "dimensoes": dados_brutos.get("dimensoes"),
                'controle_temperatura': dados_brutos.get("controle_temperatura"),
                "posicao_armazenamento": dados_brutos.get("posicao_armazenamento"),
                "nocivo": dados_brutos.get("nocivo"),
                "peso": dados_brutos.get("peso"),
                "sujeito_intemperie": dados_brutos.get("sujeito_intemperie"),
                "protecao": dados_brutos.get("protecao"),
                "empilhamento": dados_brutos.get("empilhamento"),
                "outros_cuidados": dados_brutos.get("outros_cuidados"),
                "embalagem_transp": dados_brutos.get("embalagem_transp"),
                "posicao_icagem": dados_brutos.get("posicao_icagem"),
                "cuidad_preserv": dados_brutos.get("cuidad_preserv"),
                "limpeza_secagem": dados_brutos.get("limpeza_secagem"),
                "ferramentas": dados_brutos.get("ferramentas"),
                "legislacao": dados_brutos.get("legislacao"),
                "perigoso_10004": dados_brutos.get("perigoso_10004"),
                "descarte": dados_brutos.get("descarte"),
                "logistica_reversa": dados_brutos.get("logistica_reversa")
            }

            user_prompt = f"Processar: {json.dumps(dados_api_input, indent=2, ensure_ascii=False)}"

            MAX_TENTATIVAS = 3

            # Loop de retentativa para a ficha atual
            for tentativa in range(MAX_TENTATIVAS):
                try:
                    if callback_log: callback_log(f"Enviando {pmib_codigo} para API (Tentativa {tentativa + 1}/{MAX_TENTATIVAS})...")
                    model = genai.GenerativeModel('gemini-3.5-flash', system_instruction=system_prompt, safety_settings=safety_settings)
                    resp = model.generate_content(user_prompt)

                    texto_limpo = self._limpar_resposta_json(resp.text)
                    if not texto_limpo:
                        # Levanta um erro forçado para cair no except e acionar a retentativa
                        raise ValueError("Resposta da IA retornou vazia ou fora do formato.")

                    res_json = json.loads(texto_limpo)
                    res_json["pmib_codigo"] = pmib_codigo
                    fichas_processadas.append(res_json)
                    if callback_log: callback_log(f"Sucesso API: {pmib_codigo}")

                    break  # SUCESSO! Quebra o loop de tentativas e vai para a próxima ficha

                except Exception as e:
                    if callback_log: callback_log(f"Erro na tentativa {tentativa + 1} para {pmib_codigo}: {e}")

                    if tentativa < MAX_TENTATIVAS - 1:
                        if callback_log: callback_log("Aguardando 30 segundos antes da próxima tentativa...")
                        time.sleep(30)
                    else:
                        if callback_log: callback_log(f"Falha definitiva no PMIB {pmib_codigo} após {MAX_TENTATIVAS} tentativas. Pulando ficha.")
                        # O loop de tentativas acaba e o código segue naturalmente para o próximo arquivo no for 'lista_caminhos'

        return fichas_processadas

    def salvar_excel_intermediario(self, fichas, caminho_salvar):
        try:
            df = pd.DataFrame(fichas)
            df.to_excel(caminho_salvar, index=False)
            return True, f"Salvo em: {caminho_salvar}"
        except Exception as e:
            return False, str(e)

    # -----------------------------------------------------------------
    # NOVOS MÉTODOS DE SALVAMENTO (INTEGRAÇÃO COMPLETA)
    # -----------------------------------------------------------------
    def salvar_novo_arquivo(self, fichas_novas, caminho_destino):
        """Salva uma lista de dicionários em um novo arquivo Excel."""
        try:
            df = pd.DataFrame(fichas_novas)
            df.to_excel(caminho_destino, index=False)
            return True, f"Arquivo criado com sucesso:\n{caminho_destino}"
        except Exception as e:
            return False, f"Erro ao criar arquivo: {e}"

    def anexar_a_arquivo_existente(self, fichas_novas, caminho_existente):
        """
        Lê um Excel existente, anexa os novos dados, remove duplicatas (mantendo a mais recente)
        e salva no mesmo local.
        """
        try:
            # 1. Carregar dados antigos
            try:
                df_antigo = pd.read_excel(caminho_existente)
            except Exception as e:
                return False, f"Erro ao ler arquivo existente: {e}"

            # 2. Preparar dados novos
            df_novo = pd.DataFrame(fichas_novas)

            # 3. Concatenar
            df_final = pd.concat([df_antigo, df_novo], ignore_index=True)

            # 4. Remover duplicatas (baseado no código PMIB)
            # keep='last' garante que a versão recém processada pela IA substitua a antiga
            if 'pmib_codigo' in df_final.columns:
                df_final.drop_duplicates(subset=['pmib_codigo'], keep='last', inplace=True)

            # 5. Salvar
            df_final.to_excel(caminho_existente, index=False)

            return True, f"Dados anexados com sucesso!\nTotal de registros agora: {len(df_final)}"

        except PermissionError:
            return False, "Erro de Permissão: O arquivo Excel está aberto. Feche-o e tente novamente."
        except Exception as e:
            return False, f"Erro ao anexar dados: {e}"


# =============================================================================
# CLASSE DE AUTOMAÇÃO (SELENIUM)
# =============================================================================
class UploadAutomation:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.cancel_requested = False  # Flag de parada

    def solicitar_parada(self):
        self.cancel_requested = True

    def iniciar(self):
        self.driver = webdriver.Chrome()
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 20)
        return self.driver

    # --- NOVO MÉTODO PARA CORRIGIR O ERRO DA URL DATA:, ---
    def abrir_portal(self, url):
        """Carrega a URL fornecida no navegador já aberto."""
        if self.driver:
            self.driver.get(url)
    # ------------------------------------------------------

    def fechar(self):
        if self.driver:
            self.driver.quit()

    def safe_click(self, locator):
        try:
            el = self.wait.until(EC.presence_of_element_located(locator))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            time.sleep(0.5)
            self.wait.until(EC.element_to_be_clickable(locator))
            self.driver.execute_script("arguments[0].click();", el)
        except Exception:
            pass

    def safe_send_keys(self, locator, text):
        try:
            el = self.wait.until(EC.presence_of_element_located(locator))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            time.sleep(0.5)
            self.wait.until(EC.visibility_of_element_located(locator))
            self.driver.execute_script("arguments[0].click();", el)
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.BACKSPACE)
            el.send_keys(str(text))
        except Exception:
            pass

    def check_or_uncheck(self, locator, should_check):
        try:
            el = self.wait.until(EC.presence_of_element_located(locator))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            is_checked = el.get_attribute('checked') == 'true'
            if is_checked != should_check:
                self.safe_click(locator)
        except Exception:
            pass

    def processar_lista(self, lista_fichas, caminho_status, callback_ask=None, callback_log=None, callback_pause=None):
        url = "https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList"
        # O 'driver.get(url)' foi removido do início daqui porque agora
        # o App chama 'abrir_portal' ANTES de pedir o login.

        for ficha in lista_fichas:
            if self.cancel_requested:
                if callback_log: callback_log("Automação Web interrompida pelo usuário.")
                break  # Quebra o loop principal e vai para o finally de fechamento

            pmib = ficha['pmib_codigo']
            if callback_log: callback_log(f"Processando {pmib}...")

            try:
                # 1. Busca
                self.driver.get(url)
                time.sleep(2)
                loc_search = (By.XPATH, "//input[@placeholder='Código, Nome ES/PT pela Ficha Técnica, Código do projeto e/ou contrato']")
                self.safe_send_keys(loc_search, pmib)
                self.wait.until(EC.visibility_of_element_located(loc_search)).send_keys(Keys.ENTER)

                time.sleep(4)
                loc_edit = (By.XPATH, f"//span[text()='{pmib}']/ancestor::tr//a[.//i[contains(@class, 'fa-pencil-square-o')]]")
                self.safe_click(loc_edit)

                # --- ABA 1: CONDIÇÕES (ARMAZENAMENTO) ---
                try:
                    self.safe_click((By.XPATH, '//*[@id="b10-Conditions_Header"]/button'))
                except Exception as e:
                    if callback_log: callback_log(f"ERRO: Não abriu aba Condições. {e}")
                    continue  # Pula ficha se falhar a aba principal

                try:
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_PackingLength"]'), ficha["dimensoes"]["comprimento"])
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_PackagingWidth"]'), ficha["dimensoes"]["largura"])
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_PackagingHeight"]'), ficha["dimensoes"]["altura"])
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha nas Dimensões. {e}")

                try:
                    controle_temp_data = ficha["controle_temperatura"]
                    if controle_temp_data["necessidade"] == "SIM":
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton5-input"]'))
                        if controle_temp_data["climatizacao"]["ativo"]:
                            loc_check_clima = (By.XPATH, '//*[@id="b10-b17-b1-Checkbox4"]')
                            self.check_or_uncheck(loc_check_clima, True)
                            check_clima = self.wait.until(EC.element_to_be_clickable(loc_check_clima))
                            check_clima.send_keys(Keys.TAB)
                            time.sleep(0.2)
                            campo_temp_max = self.driver.switch_to.active_element
                            campo_temp_max.send_keys(controle_temp_data["climatizacao"]["temp_max"])
                            time.sleep(0.3)
                            campo_temp_max.send_keys(Keys.TAB)
                            time.sleep(0.2)
                            campo_temp_min = self.driver.switch_to.active_element
                            campo_temp_min.send_keys(controle_temp_data["climatizacao"]["temp_min"])
                            time.sleep(0.3)
                        if controle_temp_data["umidade"]["ativo"]:
                            loc_check_umid = (By.XPATH, '//*[@id="b10-b17-b1-Checkbox5"]')
                            self.check_or_uncheck(loc_check_umid, True)
                            check_umid = self.wait.until(EC.element_to_be_clickable(loc_check_umid))
                            check_umid.send_keys(Keys.TAB)
                            time.sleep(0.2)
                            campo_hr_max = self.driver.switch_to.active_element
                            campo_hr_max.send_keys(controle_temp_data["umidade"]["hr_max"])
                            time.sleep(0.3)
                            campo_hr_max.send_keys(Keys.TAB)
                            time.sleep(0.2)
                            campo_hr_min = self.driver.switch_to.active_element
                            campo_hr_min.send_keys(controle_temp_data["umidade"]["hr_min"])
                            time.sleep(0.3)
                    else:
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton4-input"]'))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha em Temperatura. {e}")

                try:
                    posicoes = {
                        "Vertical": (By.XPATH, '//*[@id="b10-b17-b1-RadioButton-input"]'),
                        "Horizontal": (By.XPATH, '//*[@id="b10-b17-b1-RadioButton7-input"]'),
                        "Indiferente": (By.XPATH, '//*[@id="b10-b17-b1-RadioButton8-input"]')
                    }
                    if ficha.get("posicao_armazenamento") in posicoes:
                        self.safe_click(posicoes[ficha["posicao_armazenamento"]])
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha na Posição. {e}")

                try:
                    nocivo_data = ficha["nocivo"]
                    if nocivo_data["status"] == "Nocivo":
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton2-input"]'))
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-TextArea_StorageCareES"]'), nocivo_data["cuidado_es"])
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-TextArea_StorageCarePT"]'), nocivo_data["cuidado_pt"])
                    else:
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton1-input"]'))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha em Nocivo. {e}")

                try:
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_LiquidWeight"]'), ficha["peso"]["liquido"])
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_GrossWeight"]'), ficha["peso"]["bruto"])
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha nos Pesos. {e}")

                if ficha["controle_temperatura"]["necessidade"] == "NÃO":
                    try:
                        self.check_or_uncheck((By.XPATH, '//*[@id="b10-b17-b1-Checkbox3"]'), ficha.get("sujeito_intemperie") == "SIM")
                    except Exception as e:
                        if callback_log: callback_log(f"Aviso: Falha em Intempérie. {e}")

                try:
                    mapa_protecao = {
                        "SN": (By.XPATH, '//*[@id="b10-b17-b1-Checkbox6"]'),
                        "UV": (By.XPATH, '//*[@id="b10-b17-b1-Checkbox7"]'),
                        "EL": (By.XPATH, '//*[@id="b10-b17-b1-Checkbox8"]')
                    }
                    for loc in mapa_protecao.values():
                        self.check_or_uncheck(loc, False)
                    for prot in ficha.get("protecao", []):
                        if prot in mapa_protecao:
                            self.check_or_uncheck(mapa_protecao[prot], True)
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha na Proteção. {e}")

                try:
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-Input_Stacking"]'), ficha.get("empilhamento", ""))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha no Empilhamento. {e}")

                try:
                    cuidados_data = ficha["outros_cuidados"]
                    if cuidados_data["status"] == "SIM":
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton6-input"]'))
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-TextArea_OtherCareES"]'), cuidados_data["cuidado_es"])
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b1-TextArea_OtherCarePT"]'), cuidados_data["cuidado_pt"])
                    else:
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b1-RadioButton3-input"]'))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha em Outros Cuidados. {e}")

                self.safe_save_with_pause((By.XPATH, '//*[@id="b10-b17-b1-b35-Button"]/button'), "Armazenamento", callback_log, callback_pause)

                # --- ABA 2: TRANSPORTE ---
                try:
                    self.safe_click((By.XPATH, '//*[@id="b10-b17-Title"]/div[3]'))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b3-TextArea_TransportPackagingES"]'), ficha.get("embalagem_transp_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b3-TextArea_TransportPackagingPT"]'), ficha.get("embalagem_transp_pt", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b3-TextArea_PositionCareES"]'), ficha.get("posicao_icagem_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b3-TextArea_PositionCarePT"]'), ficha.get("posicao_icagem_pt", ""))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha na aba Transporte. {e}")

                self.safe_save_with_pause((By.XPATH, '//*[@id="b10-b17-$b3"]/div[3]/button'), "Transporte", callback_log, callback_pause)

                # --- ABA 3: MANUTENÇÃO ---
                try:
                    self.safe_click((By.XPATH, '//*[@id="b10-b17-Title"]/div[4]'))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_PreservationCareES"]'), ficha.get("cuidad_preserv_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_PreservationCarePT"]'), ficha.get("cuidad_preserv_pt", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_CleaningMethodES"]'), ficha.get("limpeza_secagem_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_CleaningMethodPT"]'), ficha.get("limpeza_secagem_pt", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_ToolPreservationES"]'), ficha.get("ferramentas_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b4-TextArea_ToolPreservationPT"]'), ficha.get("ferramentas_pt", ""))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha na aba Manutenção. {e}")

                self.safe_save_with_pause((By.XPATH, '//*[@id="b10-b17-$b4"]/div[4]/button'), "Manutenção", callback_log, callback_pause)

                # --- ABA 4: DESCARTE ---
                try:
                    self.safe_click((By.XPATH, '//*[@id="b10-b17-Title"]/div[5]'))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_TypeLegislationES"]'), ficha.get("legislacao_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_TypeLegislationPT"]'), ficha.get("legislacao_pt", ""))

                    if ficha.get("perigoso_10004") == "SIM":
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b5-RadioButton1-input"]'))
                    else:
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b5-RadioButton2-input"]'))

                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_DiscardTypeES"]'), ficha.get("descarte_es", ""))
                    self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_DiscardTypePT"]'), ficha.get("descarte_pt", ""))

                    logistica_rev = ficha.get("logistica_reversa", {})
                    if logistica_rev.get("status") == "SIM":
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b5-Applies-input"]'))
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_ReserveLogisticES"]'), logistica_rev.get("logistica_reversa_es", ""))
                        self.safe_send_keys((By.XPATH, '//*[@id="b10-b17-b5-TextArea_ReserveLogisticPT"]'), logistica_rev.get("logistica_reversa_pt", ""))
                    else:
                        self.safe_click((By.XPATH, '//*[@id="b10-b17-b5-DoesNotApply-input"]'))
                except Exception as e:
                    if callback_log: callback_log(f"Aviso: Falha na aba Descarte. {e}")

                self.safe_save_with_pause((By.XPATH, '//*[@id="b10-b17-$b5"]/div[5]/button'), "Descarte", callback_log, callback_pause)

                if callback_log: callback_log(f"{pmib} concluído no portal.")
                self.atualizar_status_excel(caminho_status, pmib, "COMPLETO", callback_log, callback_ask)

            except Exception as e:
                if callback_log: callback_log(f"!!! ERRO CRÍTICO processando {pmib}: {e} !!!")
                try:
                    self.driver.save_screenshot(f"erro_web_{pmib}.png")
                    if callback_log: callback_log(f"Evidência salva: erro_web_{pmib}.png")
                except:
                    pass

    def safe_save_with_pause(self, locator, section_name, callback_log=None, callback_pause=None):
        """Tenta salvar. Se der erro, usa o callback_pause para travar a execução até o usuário intervir na UI."""
        try:
            if callback_log: callback_log(f"Salvando {section_name}...")
            self.safe_click(locator)
            time.sleep(1)
        except Exception as e:
            if callback_log: callback_log(f"Falha ao salvar {section_name}. Aguardando intervenção manual.")
            if callback_pause:
                callback_pause(section_name)  # Chama o Frontend para mostrar a janela e pausar
            else:
                time.sleep(5)  # Fallback caso falte o callback

    def atualizar_status_excel(self, caminho, pmib, status, callback_log=None, callback_ask=None):
        """Atualiza o Excel com loop de retentativa caso esteja aberto."""
        pmib_alvo = str(pmib).strip()

        while True:
            try:
                wb = openpyxl.load_workbook(caminho)
                ws = wb['Lista de Materiais']

                # 1. Busca dinâmica de Cabeçalho (Varre as 15 primeiras
                #    linhas, 49 colunas) -- CP 1.2: delega para
                #    core.excel.headers (mesmo alcance do original).
                rows = headers.rows_from_worksheet(ws, max_row=15, max_col=49)
                col_map, header_row_encontrado = headers.find_columns(
                    rows, {config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB, config.COL_CONDICOES: config.COL_CONDICOES}
                )
                header_row = header_row_encontrado if header_row_encontrado is not None else 1

                # Fallback caso não encontre os nomes exatos
                col_pmib = col_map.get(config.COL_CODIGO_PMIB) or 8
                col_status = col_map.get(config.COL_CONDICOES) or 10

                encontrou = False
                # 2. Busca varrendo da linha do cabeçalho pra baixo
                for r in range(header_row + 1, ws.max_row + 1):
                    cell_raw = ws.cell(row=r, column=col_pmib).value
                    if cell_raw is None: continue

                    # 3. Blindagem contra Perda de Precisão (O segredo do
                    #    .1165) -- CP 1.2: delega para a normalização única
                    #    (core.excel.pmib_codes.normalize_pmib).
                    cell_val = pmib_codes.normalize_pmib(cell_raw)

                    # 4. Grava o status
                    if cell_val == pmib_alvo:
                        ws.cell(row=r, column=col_status).value = status
                        encontrou = True
                        break

                # Auditoria para o usuário saber o que ocorreu
                if encontrou:
                    wb.save(caminho)
                    if callback_log: callback_log(f"Excel atualizado para COMPLETO: {pmib_alvo}")
                else:
                    if callback_log: callback_log(f"Aviso Crítico: PMIB {pmib_alvo} NÃO encontrado na planilha _STATUS. (Não pôde salvar).")

                wb.close()
                break  # Sai do loop em caso de sucesso

            except PermissionError:
                if callback_log: callback_log("Erro: Arquivo Excel aberto.")
                if callback_ask:
                    # Envia a requisição para a UI perguntando o que fazer e aguarda resposta
                    resposta_retry = callback_ask("ARQUIVO_BLOQUEADO")
                    if not resposta_retry:
                        if callback_log: callback_log("Salvamento ignorado pelo usuário.")
                        break  # O usuário escolheu cancelar
                else:
                    break  # Fallback
            except Exception as e:
                if callback_log: callback_log(f"Erro ao atualizar Excel: {e}")
                break
