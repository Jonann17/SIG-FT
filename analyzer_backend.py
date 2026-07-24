import os
import json
import openpyxl
import time
import shutil
import re
from openpyxl.styles import Font, Color
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
import google.generativeai as genai

# -----------------------------------------------------------------
# CONSTANTES E CONFIGURAÇÕES
# -----------------------------------------------------------------
FORBIDDEN_NA_STRINGS = ['n/a', 'na', 'não aplicável', 'nao aplicavel', 'n.a', 'n.d', 'nd', 'não se aplica']

# Estilos de Fonte (Objetos Globais)
FONT_ERRO_VERMELHO = Font(color="FF0000", bold=True)
INLINE_FONT_ERRO_VERMELHO = InlineFont(color="FF0000", b=True)
INLINE_FONT_ERRO_TACHADO = InlineFont(color="FF0000", strike=True)

# Mapeamento Completo (Idêntico ao original)
CONFIG_MAP = {
    "texto_breve_material": {"range": "H6:P6", "type": "cell", "validation": "simple", "weight": 1},
    "unidade": {"range": "H8:J8", "type": "cell", "validation": "simple", "weight": 1},
    "tipo_fabricacao": {"cells": ["F10", "F12"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["F10", "F12"]},
    "fabricante": {"range": "L10:N10", "type": "cell", "validation": "simple", "weight": 1},
    "origem": {"cells": ["S6", "S8"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["S6", "S8"]},
    "tipo": {"cells": ["S10", "S12"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": ["S10", "S12"]},
    "comprimento_embalagem": {"range": "H17:K17", "type": "cell", "validation": "simple", "weight": 1},
    "largura_embalagem": {"range": "H19:K19", "type": "cell", "validation": "simple", "weight": 1},
    "altura_embalagem": {"range": "H21:K21", "type": "cell", "validation": "simple", "weight": 1},
    "peso_liquido": {"range": "P17:Q17", "type": "cell", "validation": "simple", "weight": 1},
    "peso_bruto": {"range": "P19:Q19", "type": "cell", "validation": "simple", "weight": 1},
    "sujeito_intemperies": {"cells": ["Q21", "S21"], "type": "checkbox", "validation": "simple", "weight": 1, "error_target": "U21"},
    "posicao_armazenamento": {"cells": ["G25", "G27", "G29"], "type": "checkbox", "validation": "simple", "weight": 3, "error_target": "J27"},
    "protecao": {"cells": ["S25", "S27", "S29"], "type": "checkbox", "validation": "simple", "weight": 3, "error_target": "O27"},
    "nocivo": {"cells": ["E31", "E33"], "type": "checkbox", "validation": "simple", "weight": 2, "error_target": "L31"},
    "empilhamento": {"range": "J35:L35", "type": "cell", "validation": "simple", "weight": 2},
    "embalagem_transporte": {"range": "M42:V44", "type": "cell", "validation": "ai", "weight": 7},
    "transporte": {"range": "M45:V47", "type": "cell", "validation": "ai", "weight": 3},
    "preservacao": {"range": "M52:V53", "type": "cell", "validation": "ai", "weight": 6},
    "metodo_limpeza": {"range": "M54:V55", "type": "cell", "validation": "ai", "weight": 3},
    "ferramentas_para_preservacao": {"range": "M56:V58", "type": "cell", "validation": "ai", "weight": 1},
    "tipo_legislacao": {"range": "M63:V64", "type": "cell", "validation": "ai", "weight": 4},
    "tipo_descarte": {"range": "M65:V66", "type": "cell", "validation": "ai", "weight": 2},
    "classificacao_periculosidade": {"cells": ["E69", "J69"], "type": "checkbox", "validation": "simple", "weight": 2},
    "logistica_reversa": {"cells": ["P69", "T69"], "type": "checkbox", "validation": "simple", "weight": 2},
}

VARIAVEIS_SPECS = {
    "start_row": 79,
    "pergunta_range": "C:L",
    "resposta_range": "M:V",
}


# -----------------------------------------------------------------
# CLASSE PRINCIPAL
# -----------------------------------------------------------------
class DatasheetAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.last_api_call_time = 0
        self.min_seconds_between_calls = 60

        if self.api_key:
            # Configuração padrão com transport REST para redes corporativas
            genai.configure(api_key=self.api_key, transport='rest')

    # -----------------------------------------------------------------
    # HELPERS DE EXCEL (Modificam a célula diretamente)
    # -----------------------------------------------------------------
    def get_cell_from_range(self, ws, range_str):
        # Pega a primeira célula do range (ex: "H6:P6" -> retorna objeto célula H6)
        first_cell_ref = range_str.split(':')[0]
        return ws[first_cell_ref]

    def set_blank_error(self, cell):
        """Aplica 'FORNECER' em vermelho na célula."""
        try:
            cell.value = "FORNECER"
            cell.font = FONT_ERRO_VERMELHO
        except Exception as e:
            print(f"Erro ao setar blank error: {e}")

    def set_invalid_error(self, cell, old_value):
        """Aplica RichText: FORNECER (ValorAntigoTachado)"""
        try:
            val_str = str(old_value) if old_value is not None else "N/A"

            # Constrói o texto rico
            rt = CellRichText([
                TextBlock(text="FORNECER (", font=INLINE_FONT_ERRO_VERMELHO),
                TextBlock(text=val_str, font=INLINE_FONT_ERRO_TACHADO),
                TextBlock(text=")", font=INLINE_FONT_ERRO_VERMELHO)
            ])
            cell.value = rt
        except Exception as e:
            print(f"Erro ao setar invalid error: {e}")
            # Fallback seguro
            cell.value = f"FORNECER ({old_value})"
            cell.font = FONT_ERRO_VERMELHO

    def extract_pmib_code(self, filename):
        match = re.search(r"\d{10}\.(\d{4})", filename)
        return match.group(1) if match else None

    # -----------------------------------------------------------------
    # LÓGICA DE PROCESSO (IDÊNTICA AO ORIGINAL)
    # -----------------------------------------------------------------
    def processar_planilha(self, input_filepath, root_output_dir, subfolder_name, original_filename, pmib_sheet, score_threshold, custom_weights=None, max_variable_points=45.0, callback_manual_desc=None):
        """
        Executa o pipeline completo de análise para um arquivo com NORMALIZAÇÃO AUTOMÁTICA.
        """
        total_score_earned = 0.0   # Pontos que o arquivo ganhou
        total_possible_fixed = 0.0  # Soma de todos os pesos fixos configurados

        yield f"--- Iniciando Arquivo: {original_filename} ---"

        # 1. Carregar Excel
        try:
            wb = openpyxl.load_workbook(input_filepath)
            ws = wb.active
        except Exception as e:
            yield f"[ERRO] Não foi possível abrir o arquivo. Erro: {e}"
            return False

        # 2. Enriquecimento de Contexto (PMIB)
        codigo_pmib_4 = self.extract_pmib_code(input_filepath)
        desc_complementar = None
        if pmib_sheet and codigo_pmib_4:
            desc_complementar = self._find_pmib_description(codigo_pmib_4, pmib_sheet)
            if desc_complementar:
                yield f"[INFO] PMIB {codigo_pmib_4} encontrado. Descrição obtida."
            else:
                yield f"[AVISO] PMIB {codigo_pmib_4} não encontrado na lista."
                if callback_manual_desc:
                    desc_complementar = callback_manual_desc(original_filename, codigo_pmib_4)

        # Estruturas para IA
        dados_ia_contexto = {}
        dados_ia_validar = {}
        celulas_ai_map = {}

        # 3. Validação de Campos Fixos (CONFIG_MAP)
        for key, config in CONFIG_MAP.items():
            is_valid = True

            # --- Lógica de Pesos Customizados ---
            weight = config["weight"]
            if custom_weights and key in custom_weights:
                try:
                    weight = float(custom_weights[key])
                except ValueError:
                    pass

            # [ALTERAÇÃO 1] Acumula o peso possível total (para o denominador da normalização)
            total_possible_fixed += weight
            # -----------------------------------------------

            # --- TIPO: CÉLULA ÚNICA ---
            if config["type"] == "cell":
                cell = self.get_cell_from_range(ws, config["range"])
                val = cell.value
                val_str = str(val).strip().lower() if val is not None else ""

                if config["validation"] == "ai":
                    celulas_ai_map[key] = {'cell': cell, 'weight': weight}

                    if val_str in FORBIDDEN_NA_STRINGS:
                        self.set_invalid_error(cell, val)
                        is_valid = False
                    elif val is None or val_str == "":
                        self.set_blank_error(cell)
                        is_valid = False
                    else:
                        dados_ia_validar[key] = val

                elif key in ["texto_breve_material", "fabricante"]:
                    dados_ia_contexto[key] = val
                    if config["validation"] == "simple":
                        if val is None or val_str == "":
                            self.set_blank_error(cell)
                            is_valid = False

                elif config["validation"] == "simple":
                    if val is None or val_str == "":
                        self.set_blank_error(cell)
                        is_valid = False

            # --- TIPO: CHECKBOX ---
            elif config["type"] == "checkbox":
                is_checked = any(ws[c].value is not None for c in config["cells"])

                if not is_checked:
                    is_valid = False
                    targets = config.get("error_target")
                    if targets:
                        if isinstance(targets, list):
                            for t in targets: self.set_blank_error(ws[t])
                        else:
                            self.set_blank_error(ws[targets])
                    else:
                        self.set_blank_error(ws[config["cells"][0]])

            # Soma pontos GANHOS se passou na validação simples
            if config.get("validation") == "simple" or config.get("type") == "checkbox":
                if is_valid:
                    total_score_earned += weight

        # Aplica Descrição Complementar
        if desc_complementar:
            orig = dados_ia_contexto.get("texto_breve_material", "")
            dados_ia_contexto["texto_breve_material"] = f"{orig} ({desc_complementar})" if orig else desc_complementar

        # 4. Mapeamento Dinâmico (Variáveis)
        start_row = self._find_variable_specs_start_row(ws)

        # 4a. Contar Total
        total_vars = 0
        r = start_row
        col_p = VARIAVEIS_SPECS["pergunta_range"].split(':')[0]
        while True:
            if not ws[f"{col_p}{r}"].value: break
            total_vars += 1
            r += 1
            if r > start_row + 200: break

        # Usa o max_variable_points passado no argumento
        points_per_var = (max_variable_points / total_vars) if total_vars > 0 else 0
        yield f"[INFO] {total_vars} variáveis encontradas. ({points_per_var:.2f} pts/cada)"

        # 4b. Ler e Validar Variáveis
        vars_para_ia = []
        vars_map = []

        col_r = VARIAVEIS_SPECS["resposta_range"].split(':')[0]
        r = start_row
        while True:
            p_val = ws[f"{col_p}{r}"].value
            if not p_val: break

            r_cell = ws[f"{col_r}{r}"]
            r_val = r_cell.value
            r_str = str(r_val).strip().lower() if r_val is not None else ""

            if r_val is None or r_str == "":
                self.set_blank_error(r_cell)
            else:
                vars_para_ia.append({"pergunta": p_val, "resposta": r_val})
                vars_map.append({'cell': r_cell, 'weight': points_per_var})

            r += 1
            if r > start_row + 200: break

        # 5. Validação Semântica (IA)
        ai_res = None
        if (dados_ia_validar or vars_para_ia):
            yield "Processando dados..."
            prompt = self._build_gemini_prompt(dados_ia_contexto, dados_ia_validar, vars_para_ia)
            ai_res = self._call_gemini_api(prompt)
        else:
            yield "Nada para validar via IA."

        # 6. Processar Retorno IA
        ai_valid_fixed = {k: True for k in dados_ia_validar}
        ai_valid_vars = [True] * len(vars_para_ia)

        if ai_res:
            yield "Aplicando retorno do processamento..."

            # Fixos
            for key, res in ai_res.get("campos_fixos", {}).items():
                if res.get("status") == "INVALIDO":
                    ai_valid_fixed[key] = False
                    c_obj = celulas_ai_map.get(key, {}).get('cell')
                    if c_obj: self.set_invalid_error(c_obj, c_obj.value)

            # Variáveis
            v_results = ai_res.get("campos_variaveis", [])
            for idx, res in enumerate(v_results):
                if res.get("status") == "INVALIDO":
                    if idx < len(vars_map):
                        ai_valid_vars[idx] = False
                        c_obj = vars_map[idx]['cell']
                        self.set_invalid_error(c_obj, c_obj.value)

        # 7. Somar Pontos IA (GANHOS)
        for k, valid in ai_valid_fixed.items():
            if valid: total_score_earned += celulas_ai_map[k]['weight']

        for idx, valid in enumerate(ai_valid_vars):
            if valid: total_score_earned += vars_map[idx]['weight']

        # [ALTERAÇÃO 2] Lógica de Normalização (0 a 100%)
        # Soma total possível = Soma dos pesos fixos + Total destinado às variáveis
        grand_total_possible = total_possible_fixed + max_variable_points

        if grand_total_possible > 0:
            final_percentage = (total_score_earned / grand_total_possible) * 100
        else:
            final_percentage = 0.0

        final_score = int(round(final_percentage, 0))

        # 8. Decisão e Salvamento
        folder_status = "FT_good" if final_score >= score_threshold else "FT_bad"

        # Log Informativo com detalhes da normalização
        yield f"Pontos Brutos: {total_score_earned:.1f}/{grand_total_possible:.1f}"
        yield f"Nota Normalizada: {final_score}% ({folder_status})"

        final_path_dir = os.path.join(root_output_dir, folder_status, subfolder_name)
        os.makedirs(final_path_dir, exist_ok=True)

        out_name = original_filename.replace(".xlsx", f"_{final_score}%.xlsx")
        out_path = os.path.join(final_path_dir, out_name)

        try:
            if final_score >= score_threshold:
                shutil.copy2(input_filepath, out_path)
                yield f"Salvo (Original): {out_name}"
            else:
                wb.save(out_path)
                yield f"Salvo (Marcado): {out_name}"
            return True
        except Exception as e:
            yield f"[ERRO FATAL AO SALVAR] {e}"
            return False

    # -----------------------------------------------------------------
    # MÉTODOS INTERNOS (Auxiliares de busca e API)
    # -----------------------------------------------------------------
    def _find_header_columns(self, ws):
        # Procura colunas CÓDIGO PMIB e DESCRIÇÃO
        pmib_idx, desc_idx, row_start = None, None, None
        for row in ws.iter_rows(min_row=1, max_row=10):
            found = False
            for cell in row:
                if cell.value:
                    v = str(cell.value).strip().upper()
                    if v == "CÓDIGO PMIB":
                        pmib_idx = cell.column; found = True
                    elif v == "DESCRIÇÃO":
                        desc_idx = cell.column; found = True
            if found: row_start = cell.row
            if pmib_idx and desc_idx: return pmib_idx, desc_idx, row_start + 1
        return None, None, None

    def _find_pmib_description(self, code_4, ws):
        pidx, didx, rstart = self._find_header_columns(ws)
        if not pidx: return None

        # Otimização: lê apenas colunas relevantes
        min_c, max_c = min(pidx, didx), max(pidx, didx)
        p_offset = pidx - min_c
        d_offset = didx - min_c

        for row in ws.iter_rows(min_row=rstart, min_col=min_c, max_col=max_c):
            c_desc = row[d_offset]
            c_pmib = row[p_offset]

            if not c_desc.value: break  # Fim da lista

            if c_pmib.value:
                val = str(c_pmib.value).strip()
                if val.endswith(f".{code_4}") or val == code_4:
                    return str(c_desc.value).strip()
        return None

    def _find_variable_specs_start_row(self, ws):
        tgt = "ESPECIFICAÇÕES TÉCNICAS - INDIQUE AS ESPECIFICAÇÕES TÉCNICAS NO ESPAÇO LIVRE ABAIXO"
        for row in ws.iter_rows(min_row=50, max_row=150, min_col=2, max_col=2):
            if row[0].value and tgt in str(row[0].value).strip().upper():
                return row[0].row + 4
        return 79

    def _build_gemini_prompt(self, context, fixed, variable):
        # Constrói o prompt exatamente como o original
        mat = context.get("texto_breve_material", "[N/A]")
        fab = context.get("fabricante", "[N/A]")

        str_fixed = ""
        for k, v in fixed.items():
            str_fixed += f'{k}: "{v}"\n'
        if not str_fixed: str_fixed = "[Vazio]"

        str_vars = ""
        for item in variable:
            str_vars += f'"{item["pergunta"]}": "{item["resposta"]}"\n'
        if not str_vars: str_vars = "[Vazio]"

        return f"""
#System message: Você é uma IA especialista na análise de informações (informações gerais, condições de armazenamento, transporte, movimentação, manutenção e descarte, e caracteristicas técnicas) de materiais utilizados em usinas hidrelétricas.
#Context: Você não deve julgar se a informação é tecnicamente verídica ou 100% correta para o equipamento. Seu objetivo é realizar uma validação de formato, relevância e aplicabilidade. Abaixo são dadas regras que devem seguidas e tomadas como exemplo:

REGRAS DE VALIDAÇÃO:

1. Regra de Relevância (Faz Sentido?):
   * A informação é VALIDA se ela pertencer à categoria da pergunta.
   * A informação é INVALIDA apenas se for completamente absurda ou não tiver nada a ver com o que foi pedido.
   * Exemplo 1: Pergunta="Peso Líquido", Resposta="100kg" -> VALIDO.
   * Exemplo 2: Pergunta="Peso Líquido", Resposta="50g" -> VALIDO (Mesmo que o peso real seja outro, a categoria 'peso' está correta).
   * Exemplo 3: Pergunta="Peso Líquido", Resposta="Vermelho" -> INVALIDO (A resposta é uma cor, não um peso).
   * Exemplo 4: Pergunta="Material", Resposta="Aço Inox" -> VALIDO.
   * Exemplo 5: Pergunta="Material", Resposta="140x50mm" -> INVALIDO (A resposta é uma dimensão, não um material).

2. Regra de Aplicabilidade da informação:
   * A resposta pode ser informada como "Não aplicável" (e suas variações "N/A", "NA", "Não se aplica", etc.) desde que a pergunta realmente não se faça necessária (não exista ou não tenha relevância) para uma posterior aplicação do material.
   * Exemplo 6: Material="Válvula", Pergunta="Tensão de isolamento", Resposta="N/A" -> VALIDO (Válvulas não apresentam tensão de isolamento).
   * Exemplo 7: Material="Válvula", Pergunta="Vazão", Resposta="N/A" -> INVALIDO (A vazão de uma válvula é uma informação importante, e portanto, deve ser fornecida).
   * Exemplo 8: Material="Válvula", Pergunta="Caracteristicas adicionais", Resposta="N/A" -> VALIDO (As caracteristicas adicionais não são necessárias para uma posterior aplicação do material).
   * Exemplo 9: Material="Sensor de temperatura", Pergunta="Faixa de Medição", Resposta="Não informado" -> INVALIDO (A faixa de medição de um sensor de temperatura é uma informação importante, e portanto, deve ser fornecida, mesmo que não foi informado).

3. Regra de fornecimento de informações:
   * Todas informações devem ser fornecidas (exceto quando não aplicaveis) e não referenciadas.
   * Exemplo 10: Pergunta="Componentes", Resposta="Item 20 conforme catálogo " -> INVALIDO (A resposta deve ser dada, e não direcionada para outra fonte).

4. REGRA DE OURO:
   * Na dúvida, considere a informação como VALIDO. Seu objetivo é filtrar apenas os erros óbvios de preenchimento, não os erros técnicos sutis.

#Task: Com base nas REGRAS DE VALIDAÇÃO acima, analise os seguintes campos do material "{mat}", do fornecedor "{fab}" a partir de dados coletados sobre o material na internet.

{str_fixed}

{str_vars}

#Notes: Retorne sua resposta APENAS no formato JSON. Não inclua ```json ou qualquer outro texto antes ou depois. O JSON deve ter duas chaves: "campos_fixos" e "campos_variaveis". Para "campos_fixos", use as chaves exatas que eu forneci (ex: "embalagem_transporte"). Para "campos_variaveis", retorne uma lista, na mesma ordem em que foram fornecidos. Para cada campo, indique um status "VALIDO" ou "INVALIDO". Exemplo de formato de resposta JSON:

{{
  "campos_fixos": {{
    "embalagem_transporte": {{ "status": "VALIDO" }},
    "transporte": {{ "status": "INVALIDO" }}
  }},
  "campos_variaveis": [
    {{ "status": "INVALIDO" }}
  ]
}}
"""

    def _call_gemini_api(self, prompt):
        now = time.time()
        if (now - self.last_api_call_time) < self.min_seconds_between_calls:
            time.sleep(self.min_seconds_between_calls - (now - self.last_api_call_time))

        self.last_api_call_time = time.time()

        for _ in range(3):
            try:
                model = genai.GenerativeModel('gemini-3.1-pro-preview')  # Modelo atualizado
                resp = model.generate_content(prompt)
                txt = resp.text.replace("```json", "").replace("```", "").strip()
                return json.loads(txt)
            except Exception as e:
                print(f"API Error: {e}")
                time.sleep(5)
        return None
