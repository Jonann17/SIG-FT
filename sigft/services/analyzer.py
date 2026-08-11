import os
import json
import openpyxl
import time
import shutil
from openpyxl.styles import Font, Color
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont

from sigft import config
from sigft.core.excel import headers, pmib_codes
from sigft.core.rpa.ficha_layout import CONFIG_MAP, VARIAVEIS_SPECS
# CP 3.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 3): `google.generativeai`
# deixou de ser importado aqui -- `_call_gemini_api` abaixo delega para
# `LLMClient`/`GeminiProvider` (ÚNICO lugar do projeto que importa `genai`).
# `import time` acima fica SEM uso neste arquivo (só existia para o
# rate-limit/retry que morava em `_call_gemini_api`, agora dentro do
# `LLMClient`) -- deixado intacto por disciplina de "só o call site de IA
# muda" (mesmo precedente já registrado em PENDENCIAS.md para imports mortos
# de checkpoints anteriores), candidato a limpeza no CP 8.1 (ruff).
from sigft.core.llm.client import get_llm
# CP 3.5 (Fase 3): o TEXTO do prompt de `_build_gemini_prompt` abaixo mora em
# `sigft.core.llm.prompts.montar_validar_ficha` -- só o pré-processamento
# (extrair mat/fab, montar str_fixed/str_vars) continua aqui.
from sigft.core.llm import prompts

# -----------------------------------------------------------------
# CONSTANTES E CONFIGURAÇÕES
# -----------------------------------------------------------------
FORBIDDEN_NA_STRINGS = ['n/a', 'na', 'não aplicável', 'nao aplicavel', 'n.a', 'n.d', 'nd', 'não se aplica']

# Estilos de Fonte (Objetos Globais)
FONT_ERRO_VERMELHO = Font(color="FF0000", bold=True)
INLINE_FONT_ERRO_VERMELHO = InlineFont(color="FF0000", b=True)
INLINE_FONT_ERRO_TACHADO = InlineFont(color="FF0000", strike=True)

# CP 2.4: CONFIG_MAP/VARIAVEIS_SPECS deixaram de ser definidos aqui — agora
# importados de sigft.core.rpa.ficha_layout (fonte única, compartilhada com
# autospec_backend.py). Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 ->
# CP 2.4, e o docstring de ficha_layout.py para o histórico da unificação.


# -----------------------------------------------------------------
# CLASSE PRINCIPAL
# -----------------------------------------------------------------
class DatasheetAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key
        # CP 3.1: rate-limit (60s entre chamadas) e configuração do cliente
        # Gemini (transport REST) agora vivem dentro de `LLMClient`/
        # `GeminiProvider`, resolvidos aqui via `get_llm("validar_ficha",
        # api_key)` -- `self.last_api_call_time`/`self.min_seconds_between_calls`
        # REMOVIDOS (não são mais lidos por ninguém; ver `_call_gemini_api`).
        self._llm = get_llm("validar_ficha", api_key)

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
        # CP 1.2: delega para a implementação única (core.excel.pmib_codes),
        # que aplica os.path.basename() ANTES do regex — corrige o bug
        # latente caracterizado no CP 0.1 (regex podia "vazar" um match do
        # DIRETÓRIO em vez do arquivo). Ver
        # tests/test_analyzer_backend_characterization.py.
        return pmib_codes.extract_pmib_code(filename)

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

        if not ai_res:
            # A IA NÃO respondeu (chave inválida, rede, cota...). O código
            # abaixo deixa `ai_valid_*` todo `True`, ou seja: a ficha ganha
            # 100% dos pontos que a IA deveria julgar, SEM que a IA tenha
            # julgado nada. A nota final sai INFLADA e nada na tela dizia
            # isso -- o único sinal era um `print` na janela preta.
            #
            # Comportamento PRÉ-EXISTENTE (está no código original); este
            # aviso não muda a pontuação, só para de escondê-la. Mudar a
            # forma de pontuar é decisão de produto (contar como válido x
            # abortar a ficha x pontuar só o que não é IA), registrada em
            # docs/refatoracao/PENDENCIAS.md.
            yield "=" * 60
            yield "⚠️  ATENÇÃO: a IA NÃO respondeu para esta ficha."
            yield "   Os campos que dependem da IA foram contados como VÁLIDOS,"
            yield "   então a nota abaixo está INFLADA e não pode ser usada"
            yield "   como aprovação. Confira o erro no log de IA"
            yield "   (logs/llm_usage.jsonl) e rode de novo."
            yield "=" * 60

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
        # Procura colunas CÓDIGO PMIB e DESCRIÇÃO — CP 1.2: delega para a
        # implementação única (core.excel.headers), mesmo alcance de
        # varredura do original (10 primeiras linhas, todas as colunas).
        rows = headers.rows_from_worksheet(ws, max_row=10)
        col_map, header_row = headers.find_columns(
            rows,
            {config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB, config.COL_DESCRICAO: config.COL_DESCRICAO},
        )
        if header_row is None:
            return None, None, None
        return col_map[config.COL_CODIGO_PMIB], col_map[config.COL_DESCRICAO], header_row + 1

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
        # CP 2.4: fallback nomeado via config.LINHA_SPECS_FICHA (mesmo valor
        # numérico de sempre, 79 — só deixa de ser um literal solto).
        return config.LINHA_SPECS_FICHA

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

        # CP 3.5 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 3): o TEXTO do
        # prompt (antes embutido aqui como f-string gigante) agora mora em
        # `sigft.core.llm.prompts.montar_validar_ficha` -- só o
        # pré-processamento acima (extrair mat/fab, montar str_fixed/
        # str_vars) continua neste método.
        return prompts.montar_validar_ficha(mat, fab, str_fixed, str_vars)

    def _call_gemini_api(self, prompt):
        # CP 3.1: rate-limit (60s) + retry (3 tentativas, 5s entre elas) +
        # limpeza/parse do JSON da resposta agora vivem dentro de
        # `LLMClient.generate()` (`self._llm`, resolvido em `__init__` via
        # `get_llm("validar_ficha", ...)`) -- este método vira um
        # try/except fino, preservando o `return None` em falha total e o
        # `print` de erro (só perde o detalhe de QUAL das 3 tentativas
        # falhou -- ver docs/refatoracao/PENDENCIAS.md).
        try:
            resp = self._llm.generate(prompt, tags={"modulo": "analyzer_backend", "tarefa": "validar_ficha"})
            return resp.parsed_json
        except Exception as e:
            print(f"API Error: {e}")
            return None
