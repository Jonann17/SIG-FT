import os
import re
import json
import requests
import tempfile
import openpyxl
from openpyxl.styles import Font
import PyPDF2
from bs4 import BeautifulSoup

# Integração LlamaParse
from llama_parse import LlamaParse

from sigft import config
from sigft.core.excel import headers, pmib_codes
from sigft.core.rpa.ficha_layout import CONFIG_MAP, VARIAVEIS_SPECS
from sigft.core.llm.client import get_llm
# CP 3.5 (Fase 3): o TEXTO do preâmbulo do prompt de
# `generate_ai_response` abaixo mora em
# `sigft.core.llm.prompts.montar_autospec` -- o laço que monta `desc_list`
# (consulta GENERATIVE_FIELDS, logo abaixo) continua neste módulo.
from sigft.core.llm import prompts
# CP 4.4 (Fase 4, docs/refatoracao/PLANO_REFATORACAO.md): `process_queue` é a
# única função de LOTE deste módulo (os demais métodos de `AutoSpecCore` são
# helpers de UM item) -- passa a emitir o padrão único de log via
# `RelatorioLote`. Ver docstring de `process_queue` para como isso convive
# com o contrato de generator que `frontend.py` já consome.
from sigft.core.callbacks import UICallbacks
from sigft.core.relatorio_lote import RelatorioLote

# -----------------------------------------------------------------
# 1. CONFIGURAÇÕES E MAPAS
# -----------------------------------------------------------------
# [REMOVIDO] Constantes de chaves API hardcoded foram removidas daqui.
# As chaves agora devem ser passadas exclusivamente via __init__ da classe AutoSpecCore.

GENERATIVE_FIELDS = [
    "empilhamento", "embalagem_transporte", "transporte", "preservacao",
    "metodo_limpeza", "ferramentas_para_preservacao", "tipo_legislacao",
    "tipo_descarte", "protecao", "posicao_armazenamento", "unidade", "tipo"
]

# CP 2.4: CONFIG_MAP/VARIAVEIS_SPECS deixaram de ser definidos aqui — agora
# importados de sigft.core.rpa.ficha_layout (fonte única, compartilhada com
# analyzer_backend.py). Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 2 ->
# CP 2.4, e o docstring de ficha_layout.py para o histórico da unificação.
#
# ATENÇÃO: o "range" canônico agora é o range COMPLETO da célula mesclada
# (ex.: "H6:P6", herdado do analyzer_backend) em vez de só a primeira célula
# (ex.: "H6", como este arquivo guardava antes). Os acessos que já faziam
# `.split(":")[0]` (ex.: dentro de `analyze_sheet`, mapeamento estático, e
# `fill_save`) continuam corretos sem alteração; os 2 acessos DIRETOS de
# `analyze_sheet` (txt_brv/fab, logo abaixo) precisaram do mesmo split — ver
# docs/refatoracao/PENDENCIAS.md, entrada do CP 2.4.


# -----------------------------------------------------------------
# 2. CLASSES UTILITÁRIAS (Busca e PDF)
# -----------------------------------------------------------------
class WebSearcher:
    def __init__(self, api_key, cse_id):
        self.api_key = api_key
        self.cse_id = cse_id
        self.search_url = "https://www.googleapis.com/customsearch/v1"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

    def search_and_download(self, query, required_terms=[], max_results=3):
        if not self.api_key or not self.cse_id:
            return []
        params = {'key': self.api_key, 'cx': self.cse_id, 'q': query, 'num': max_results, 'gl': 'br', 'hl': 'pt'}
        try:
            response = requests.get(self.search_url, params=params)
            response.raise_for_status()
            data = response.json()
            items = data.get('items', [])
            results = []
            for item in items:
                link = item.get('link', '').lower()
                title = item.get('title', '').lower()
                snippet = item.get('snippet', '').lower()
                is_relevant = False
                if not required_terms:
                    is_relevant = True
                else:
                    for term in required_terms:
                        term_clean = str(term).lower().strip()
                        if term_clean and (term_clean in title or term_clean in snippet or term_clean in link):
                            is_relevant = True; break
                if is_relevant:
                    filepath = self._download_file(link)
                    if filepath:
                        results.append({"path": filepath, "url": link, "title": title})
            return results
        except Exception:
            return []

    def _download_file(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                suffix = ".pdf" if url.lower().endswith(".pdf") else ".html"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    tmp_file.write(response.content)
                    return tmp_file.name
        except Exception:
            return None
        return None


class PDFProcessor:
    def __init__(self, llama_key):
        self.llama_key = llama_key
        if self.llama_key:
            os.environ["LLAMA_CLOUD_API_KEY"] = self.llama_key

    def extract_text(self, filepath):
        text_content = ""; method_used = ""; is_pdf = filepath.lower().endswith('.pdf')

        if self.llama_key and is_pdf:
            try:
                parser = LlamaParse(result_type="text")
                documents = parser.load_data(filepath)
                text_content = "\n".join([doc.text for doc in documents])
                method_used = "LlamaParse"
            except Exception:
                pass

        if not text_content and is_pdf:
            try:
                with open(filepath, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        t = page.extract_text()
                        if t: text_content += t + "\n"
                method_used = "PyPDF2"
            except Exception: pass

        if not text_content and not is_pdf:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    soup = BeautifulSoup(f, 'html.parser')
                    for script in soup(["script", "style", "nav", "footer", "header"]): script.extract()
                    text_content = soup.get_text(separator=' ', strip=True)
                method_used = "WebScrape(BS4)"
            except Exception: pass

        return text_content, method_used


# -----------------------------------------------------------------
# 3. BACKEND PRINCIPAL
# -----------------------------------------------------------------
class AutoSpecCore:
    def __init__(self, gemini_key, llama_key, google_search_key, google_cse_id):
        self.gemini_key = gemini_key
        self.llama_key = llama_key
        self.google_key = google_search_key
        self.cse_id = google_cse_id

        # Inicializa componentes
        # [CP 3.2] Guard mantido EXATAMENTE como antes -- só fala de Gemini
        # num mundo agora multi-provedor porque `LLM_MODELOS_HOJE["autospec"]`
        # ainda aponta para o Gemini em produção (ver
        # docs/refatoracao/PENDENCIAS.md).
        if not gemini_key: raise ValueError("Chave Gemini é obrigatória.")

        # [CP 3.2] LangChain removido -- `self._llm` é um `LLMClient` (via
        # `get_llm`), que já resolve o mesmo modelo
        # (`gemini-3.1-pro-preview`, idêntico ao que o LangChain usava) e a
        # mesma `temperature=0.1` (via `_POLITICA_RETRY_POR_TAREFA["autospec"]`
        # em `core/llm/client.py`) -- ver PENDENCIAS.md.
        self._llm = get_llm("autospec", self.gemini_key)
        self.searcher = WebSearcher(self.google_key, self.cse_id)
        self.pdf_parser = PDFProcessor(self.llama_key)

    # --- Helpers de Excel e Dados ---
    def extract_pmib_code(self, input_filepath):
        # CP 1.2: delega para a implementação única (core.excel.pmib_codes).
        # Já fazia os.path.basename() antes do regex — comportamento
        # inalterado (era o lado "correto" da divergência com o analyzer,
        # escolhido como canônico). Ver
        # tests/test_autospec_backend_characterization.py.
        return pmib_codes.extract_pmib_code(input_filepath)

    def find_header_columns(self, pmib_sheet):
        # CP 1.2: delega para a implementação única (core.excel.headers).
        # "CÓDIGO PMIB"/"DESCRIÇÃO" são obrigatórias; "CÓDIGO MATERIAL" (ou
        # "MATERIAL") é oportunista, com default de coluna 5 se ausente —
        # mesmo comportamento do original, incluindo o resultado PARCIAL
        # (pmib_col/desc_col podem vir None) quando as 10 primeiras linhas
        # não têm as colunas obrigatórias.
        rows = headers.rows_from_worksheet(pmib_sheet, max_row=10)
        keywords = {
            config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
            config.COL_DESCRICAO: config.COL_DESCRICAO,
            "CÓDIGO MATERIAL": ["CÓDIGO MATERIAL", "MATERIAL"],
        }
        col_map, header_row = headers.find_columns(
            rows, keywords, required=[config.COL_CODIGO_PMIB, config.COL_DESCRICAO]
        )
        pmib_col = col_map.get(config.COL_CODIGO_PMIB)
        desc_col = col_map.get(config.COL_DESCRICAO)
        mat_col = col_map.get("CÓDIGO MATERIAL") or 5
        start_row = header_row + 1 if header_row is not None else None
        return pmib_col, desc_col, mat_col, start_row

    def get_pmib_data(self, pmib_path, code_suffix):
        try:
            wb = openpyxl.load_workbook(pmib_path, data_only=True)
            ws = wb.active
            pmib_col, desc_col, mat_col, start_row = self.find_header_columns(ws)
            if not pmib_col or not desc_col: return "", ""

            for row in ws.iter_rows(min_row=start_row):
                if len(row) < max(pmib_col, desc_col, mat_col): continue
                c_pmib = row[pmib_col-1]
                val_pmib = str(c_pmib.value).strip() if c_pmib.value else ""

                if code_suffix in val_pmib:
                    desc_val = str(row[desc_col-1].value).strip() if row[desc_col-1].value else ""
                    mat_val = str(row[mat_col-1].value).strip() if row[mat_col-1].value else ""
                    return desc_val, mat_val
            return "", ""
        except Exception: return "", ""

    def is_empty(self, val):
        s_val = str(val).strip().upper()
        return not val or s_val == "" or s_val.startswith("FORNECER")

    # --- Análise da Ficha ---
    def analyze_sheet(self, filepath, status_pmib_path):
        wb = openpyxl.load_workbook(filepath)
        if "Ficha Técnica Padrão" not in wb.sheetnames:
            raise ValueError("Aba 'Ficha Técnica Padrão' não encontrada.")
        ws = wb["Ficha Técnica Padrão"]

        pmib_suffix = self.extract_pmib_code(filepath)
        desc_comp, cod_mat = "", ""
        if pmib_suffix and status_pmib_path:
            desc_comp, cod_mat = self.get_pmib_data(status_pmib_path, pmib_suffix)

        # Contexto Base
        # CP 2.4: CONFIG_MAP["...]["range"] agora guarda o range COMPLETO da
        # célula mesclada (ex. "H6:P6", não mais só "H6") — acesso direto
        # `ws[range]` devolveria uma tupla de tuplas de células (não um
        # `Cell`), quebrando `.value`. `.split(":")[0]` resolve para a
        # primeira célula, igual ao comportamento anterior à unificação.
        txt_brv = ws[CONFIG_MAP["texto_breve_material"]["range"].split(":")[0]].value
        txt_brv = str(txt_brv).strip() if txt_brv else ""
        fab = ws[CONFIG_MAP["fabricante"]["range"].split(":")[0]].value
        fab = str(fab).strip() if fab else ""

        missing = {}

        # Mapeamento Estático
        for key, cfg in CONFIG_MAP.items():
            if cfg["type"] == "cell":
                ref = cfg["range"].split(":")[0]
                if self.is_empty(ws[ref].value):
                    missing[key] = {"type": "text", "desc": cfg.get("desc", key), "ref": cfg["range"]}
            elif cfg["type"] == "checkbox":
                is_filled = any(self.is_empty(ws[c].value) is False for c in cfg["cells"])
                if not is_filled:
                    missing[key] = {"type": "checkbox", "options": cfg["cells"], "desc": cfg.get("desc", ""), "ref": cfg["cells"]}

        # Mapeamento Dinâmico (Variáveis)
        r = VARIAVEIS_SPECS["start_row"]
        while r <= ws.max_row:
            p_val = ws.cell(row=r, column=VARIAVEIS_SPECS["pergunta_col_idx"]).value
            r_val = ws.cell(row=r, column=VARIAVEIS_SPECS["resposta_col_idx"]).value
            if p_val:
                if self.is_empty(r_val):
                    clean_p = str(p_val).strip().replace(":", "")
                    missing[f"var_row_{r}"] = {"type": "text", "desc": clean_p, "ref": ws.cell(row=r, column=VARIAVEIS_SPECS["resposta_col_idx"]).coordinate}
            r += 1

        return wb, missing, txt_brv, fab, desc_comp, cod_mat

    # --- RAG: Busca e Contexto ---
    def retrieve_context(self, txt_brv, fab, cod_mat, refs_locais):
        # 1. Processar Locais
        local_txt = self.process_local_documents(refs_locais)

        # 2. Busca Web
        web_txt = ""
        sources = []

        if self.google_key and self.cse_id:
            required = []
            if fab and len(fab) > 2: required.append(fab)
            if cod_mat and len(cod_mat) > 2: required.append(cod_mat)

            queries = []
            if cod_mat: queries.append(f'"{cod_mat}" {fab} datasheet specs')
            queries.append(f"{txt_brv} {fab} datasheet specs")

            for q in queries:
                files = self.searcher.search_and_download(q, required_terms=required, max_results=3)
                if files:
                    for item in files:
                        t, m = self.pdf_parser.extract_text(item['path'])
                        if t and len(t) > 100:
                            web_txt += f"--- WEB DOC: {item['title']} ---\nURL: {item['url']}\n{t[:50000]}\n\n"
                            sources.append(item['url'])
                        try: os.remove(item['path'])
                        except Exception: pass
                    break  # Se achou algo, para

        return (local_txt + "\n\n" + web_txt), sources

    def process_local_documents(self, paths):
        ctx = []
        for p in paths:
            try:
                t, m = self.pdf_parser.extract_text(p)
                if t: ctx.append(f"--- LOCAL DOC: {os.path.basename(p)} ---\n{t[:60000]}")
            except Exception: pass
        return "\n\n".join(ctx)

    # --- Geração IA ---
    def generate_ai_response(self, txt_brv, fab, desc_comp, missing, context):
        if not missing: return {}

        # CP 3.5 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 3): o laço que
        # monta `desc_list` continua aqui (consulta GENERATIVE_FIELDS, constante
        # deste módulo) -- só o TEXTO do preâmbulo do prompt saiu daqui, para
        # `sigft.core.llm.prompts.montar_autospec`, que recebe o resultado já
        # concatenado.
        desc_list = []
        for k, v in missing.items():
            info = f"- ID '{k}': {v['desc']}"
            if k in GENERATIVE_FIELDS: info += " [INFO TÉCNICA PADRÃO]"
            else: info += " [ESTRITO]"
            if v['type'] == 'checkbox': info += f" (Opções: {v['options']})"
            desc_list.append(info)

        prompt = prompts.montar_autospec(txt_brv, fab, desc_comp, context, "\n".join(desc_list))

        try:
            # [CP 3.2] LangChain removido -- `_limpar_e_parsear_json` do
            # `LLMClient` substitui `JsonOutputParser()` (implementação
            # única, mais robusta: cobre objeto E lista, tolera prosa/fences
            # ao redor do JSON -- ver docs/refatoracao/PENDENCIAS.md).
            # `autospec` GANHA retry (2 retentativas) que antes não tinha.
            resp = self._llm.generate(
                prompt, tags={"modulo": "autospec_backend", "tarefa": "autospec"}
            )
            return resp.parsed_json
        except Exception as e:
            print(f"Erro IA: {e}")
            return {}

    def fill_save(self, wb, filepath, ai_data, missing):
        ws = wb["Ficha Técnica Padrão"]
        font = Font(color="0000FF")

        for k, val in ai_data.items():
            if k in missing and val:
                info = missing[k]
                if info['type'] == 'text':
                    ref = info['ref'].split(':')[0]
                    if k == 'empilhamento':
                        match = re.search(r'\d+', str(val))
                        ws[ref].value = int(match.group()) if match else None
                    else:
                        ws[ref].value = val
                    ws[ref].font = font
                elif info['type'] == 'checkbox':
                    clean = str(val).strip().upper()
                    if clean in info['options']:
                        for o in info['options']: ws[o].value = None
                        ws[clean].value = "X"
                        ws[clean].font = font

        base, ext = os.path.splitext(filepath)
        new_path = f"{base}_completed{ext}"
        wb.save(new_path)
        return new_path

    # --- MÉTODOS PÚBLICOS DE FLUXO ---
    def process_queue(self, queue, status_pmib_path):
        """
        Processa a lista de tarefas. Queue Item: {'sheet': path, 'refs':
        [paths]}. Yields: Logs para UI -- continua generator, mesmo
        contrato que `frontend.py` já consome, sem pattern-match em valor
        sentinela.

        CP 4.4 (Fase 4): por dentro usa `RelatorioLote` (início com
        total/contexto, por item, resumo com falhas listadas). Um generator
        não loga direto por `callbacks`, então um `UICallbacks` interno
        acumula cada linha num buffer drenado via `yield from _flush()` logo
        em seguida -- ordem das mensagens antigas preservada, só ganham
        vizinhas novas (as linhas de abertura/fechamento viram as
        equivalentes, mais ricas, de `RelatorioLote`).
        """
        buffer: list[str] = []
        callbacks = UICallbacks(log=lambda msg, nivel="info", contexto=None: buffer.append(str(msg)))

        def _flush():
            while buffer:
                yield buffer.pop(0)

        with RelatorioLote(
            callbacks,
            titulo="AutoSpec — preenchendo fichas técnicas",
            total=len(queue),
            contexto={"status_pmib": status_pmib_path},
        ) as lote:
            yield from _flush()

            for i, task in enumerate(queue):
                ficha = task['sheet']
                refs = task['refs']
                fname = os.path.basename(ficha)

                yield f"\n[{i+1}/{len(queue)}] {fname}..."

                try:
                    # 1. Analisa Ficha
                    wb, missing, txt, fab, desc, cod = self.analyze_sheet(ficha, status_pmib_path)

                    if not missing:
                        yield " -> Ficha já está completa."
                        lote.pulado(fname, "ficha já completa (sem campos faltantes)")
                        yield from _flush()
                        continue

                    yield f" -> {len(missing)} campos faltantes. Coletando contexto..."

                    # 2. Contexto
                    full_ctx, sources = self.retrieve_context(txt, fab, cod, refs)
                    if sources: yield f" -> Fontes Web: {len(sources)}"

                    # 3. IA
                    yield " -> Consultando Gemini..."
                    ai_resp = self.generate_ai_response(txt, fab, desc, missing, full_ctx)

                    # 4. Salvar
                    out_path = self.fill_save(wb, ficha, ai_resp, missing)
                    yield f" -> Salvo: {os.path.basename(out_path)}"
                    lote.sucesso(fname, f"salvo como {os.path.basename(out_path)}")
                    yield from _flush()

                except Exception as e:
                    yield f" -> ERRO: {e}"
                    lote.falha(fname, f"{type(e).__name__}: {e}")
                    yield from _flush()

        yield from _flush()
