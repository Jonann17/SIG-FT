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


# Extensões que o LlamaParse consegue OCRar. Regras de negócio §2.3/§6.1:
# catálogos antigos digitalizados chegam como TIFF/PNG/JPG. Até 2026-08-11 o
# `PDFProcessor` só distinguia ".pdf" de "resto", e o resto ia para o
# BeautifulSoup como se fosse HTML -- uma imagem virava texto-lixo, em
# silêncio.
EXTENSOES_IMAGEM = (".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp", ".webp")
EXTENSOES_OCR = (".pdf",) + EXTENSOES_IMAGEM

_CONTENT_TYPE_PARA_SUFIXO = {
    "application/pdf": ".pdf",
    "image/tiff": ".tif",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "text/plain": ".txt",
}


# P-01: todas as células que são MARCAÇÃO de algum grupo de checkbox.
# Usado para não confundir a marca de um grupo com o rótulo do vizinho ao
# varrer a planilha (`J69` fica a 6 colunas de `P69`).
_CELULAS_DE_MARCACAO = {
    celula
    for cfg in CONFIG_MAP.values()
    if cfg.get("type") == "checkbox"
    for celula in cfg.get("cells", [])
}


def _indice_da_coluna(letras):
    """`"A"` -> 1, `"H"` -> 8, `"AA"` -> 27. Equivale a
    `openpyxl.utils.column_index_from_string`, reimplementado em stdlib de
    propósito: `tests/conftest.py` stuba `openpyxl` como um `MagicMock`, que
    não é pacote, então `from openpyxl.utils import ...` quebraria a coleta
    da suíte inteira. Mesmo espírito de `core/excel/headers.py`, que também
    é stdlib-only para poder ser testado sem as dependências pesadas."""
    indice = 0
    for caractere in str(letras).upper():
        if not ("A" <= caractere <= "Z"):
            raise ValueError(f"Letra de coluna invalida: {letras!r}")
        indice = indice * 26 + (ord(caractere) - ord("A") + 1)
    if indice <= 0:
        raise ValueError(f"Letra de coluna invalida: {letras!r}")
    return indice


def _chave_comparacao(texto):
    """Forma canônica para casar resposta da IA com rótulo da planilha:
    sem acento, sem caixa, sem espaço sobrando e sem pontuação de borda.
    "Não reparável", "NAO REPARAVEL" e "nao reparavel." casam entre si."""
    import unicodedata

    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().strip(" .:;\t\n").split())


def _callbacks_silenciosos():
    """`UICallbacks` que engole tudo — default de quem chama sem passar
    callbacks (testes antigos, uso programático). Mantém a assinatura
    retrocompatível sem espalhar `if callbacks:` pelo módulo."""
    return UICallbacks(log=lambda *a, **k: None)


def _sufixo_para_url(url, content_type=None):
    """Sufixo de arquivo temporário para um download.

    Antes de 2026-08-11 era `".pdf" if url.lower().endswith(".pdf") else
    ".html"` — o que erra em dois casos comuns em site de fabricante:
    URL de PDF com query string (`.../datasheet.pdf?download=1`, que não
    termina em ".pdf") e imagem digitalizada (vira ".html" e é lida como
    HTML). Agora olha o caminho da URL sem a query e, quando disponível, o
    `Content-Type` da resposta, que é a fonte mais confiável.
    """
    caminho = str(url or "").split("?")[0].split("#")[0].lower()
    for ext in EXTENSOES_OCR + (".txt",):
        if caminho.endswith(ext):
            return ext
    if content_type:
        base = str(content_type).split(";")[0].strip().lower()
        if base in _CONTENT_TYPE_PARA_SUFIXO:
            return _CONTENT_TYPE_PARA_SUFIXO[base]
    return ".html"


# -----------------------------------------------------------------
# 2. CLASSES UTILITÁRIAS (Busca e PDF)
# -----------------------------------------------------------------
class WebSearcher:
    def __init__(self, api_key, cse_id):
        self.api_key = api_key
        self.cse_id = cse_id
        self.search_url = "https://www.googleapis.com/customsearch/v1"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

    def search_and_download(self, query, required_terms=[], max_results=3, callbacks=None):
        cb = callbacks or _callbacks_silenciosos()
        if not self.api_key or not self.cse_id:
            return []
        params = {'key': self.api_key, 'cx': self.cse_id, 'q': query, 'num': max_results, 'gl': 'br', 'hl': 'pt'}
        try:
            # timeout adicionado em 2026-08-11: sem ele, uma chamada pendurada
            # à Google CSE travava o módulo INTEIRO por tempo indefinido --
            # `_download_file` logo abaixo já usava timeout=15, esta não usava
            # nenhum. Mesmo valor, pelo mesmo motivo.
            response = requests.get(self.search_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            items = data.get('items', [])
        except Exception as e:
            # Até 2026-08-11 era `except Exception: return []` mudo: falha de
            # rede, cota estourada e "não achei nada" ficavam indistinguíveis
            # para quem olhava o console. A cota diária do CSE free tier (100
            # queries) é justamente o caso que mais confunde na prática.
            cb.log(
                f"Busca web falhou ({type(e).__name__}: {e}). Query: {query}",
                nivel="error",
            )
            return []

        results = []
        descartados = 0
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
            if not is_relevant:
                # Filtro anti-intruso (regras de negócio §4.3): catálogo de
                # concorrente barrado por não citar fabricante nem código.
                descartados += 1
                continue
            filepath = self._download_file(link, callbacks=cb)
            if filepath:
                results.append({"path": filepath, "url": link, "title": title})

        if descartados:
            cb.log(
                f"Filtro anti-intruso descartou {descartados} de {len(items)} resultado(s) "
                f"(nao citam fabricante nem codigo do material).",
                nivel="info",
            )
        return results

    def _download_file(self, url, callbacks=None):
        cb = callbacks or _callbacks_silenciosos()
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                cb.log(f"Download recusado (HTTP {response.status_code}): {url}", nivel="warn")
                return None
            suffix = _sufixo_para_url(url, response.headers.get("Content-Type"))
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(response.content)
                return tmp_file.name
        except Exception as e:
            cb.log(f"Download falhou ({type(e).__name__}): {url}", nivel="warn")
            return None


class PDFProcessor:
    def __init__(self, llama_key):
        self.llama_key = llama_key
        if self.llama_key:
            os.environ["LLAMA_CLOUD_API_KEY"] = self.llama_key

    def extract_text(self, filepath, callbacks=None):
        cb = callbacks or _callbacks_silenciosos()
        text_content = ""
        method_used = ""
        nome = os.path.basename(str(filepath))
        alvo = str(filepath).lower()
        is_pdf = alvo.endswith('.pdf')
        # P-03: imagem também vai para o LlamaParse, que faz OCR. Antes só o
        # PDF entrava nesse caminho e o TIFF/PNG/JPG caía no BeautifulSoup.
        is_imagem = alvo.endswith(EXTENSOES_IMAGEM)
        ocr_possivel = is_pdf or is_imagem

        if self.llama_key and ocr_possivel:
            try:
                parser = LlamaParse(result_type="text")
                documents = parser.load_data(filepath)
                text_content = "\n".join([doc.text for doc in documents])
                method_used = "LlamaParse"
            except Exception as e:
                cb.log(
                    f"LlamaParse falhou em {nome} ({type(e).__name__}: {e}) "
                    f"— tentando o fallback local.",
                    nivel="warn",
                )
        elif is_imagem and not self.llama_key:
            cb.log(
                f"{nome} é imagem e exige OCR, mas não há chave do LlamaParse "
                f"configurada — documento ignorado.",
                nivel="warn",
            )
            return "", ""

        if not text_content and is_pdf:
            try:
                with open(filepath, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        t = page.extract_text()
                        if t: text_content += t + "\n"
                method_used = "PyPDF2"
                if not text_content:
                    cb.log(
                        f"{nome}: PDF sem camada de texto (provavelmente escaneado). "
                        f"Só o LlamaParse leria — documento ignorado.",
                        nivel="warn",
                    )
            except Exception as e:
                cb.log(f"PyPDF2 falhou em {nome} ({type(e).__name__}: {e}).", nivel="warn")

        if not text_content and not ocr_possivel:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    soup = BeautifulSoup(f, 'html.parser')
                    for script in soup(["script", "style", "nav", "footer", "header"]): script.extract()
                    text_content = soup.get_text(separator=' ', strip=True)
                method_used = "WebScrape(BS4)"
            except Exception as e:
                cb.log(f"Leitura HTML falhou em {nome} ({type(e).__name__}: {e}).", nivel="warn")

        return text_content, method_used


# -----------------------------------------------------------------
# 3. BACKEND PRINCIPAL
# -----------------------------------------------------------------
class AutoSpecCore:
    def __init__(
        self,
        gemini_key,
        llama_key,
        google_search_key,
        google_cse_id,
        *,
        chaves=None,
        selecao_resolvida=None,
    ):
        """
        `gemini_key` continua sendo a chave do GEMINI (o `frontend.py` passa
        `self.controller.get_key("GEMINI")`), e segue valendo tal qual quando
        o provedor resolvido é o Gemini -- é o mesmo caminho que `get_llm`
        usa para os 5 consumidores desde o CP 3.1.

        `chaves`/`selecao_resolvida` (keyword-only) são pontos de injeção
        para teste, com o MESMO contrato de `core/llm/client.py:get_llm()`:
        `chaves` substitui `config.carregar_chaves()`; `selecao_resolvida`
        substitui a leitura de `sigft.core.llm.selecao.resolver()`. Em uso
        real ficam `None` e tudo é lido do disco.
        """
        self.gemini_key = gemini_key
        self.llama_key = llama_key
        self.google_key = google_search_key
        self.cse_id = google_cse_id

        # Resolve o provedor UMA vez e reaproveita: o guard abaixo e o
        # `get_llm` no fim precisam concordar sobre qual provedor vai rodar.
        # Se cada um resolvesse por conta, uma seleção mudando no disco entre
        # as duas leituras produziria o pior dos mundos -- guard checando a
        # chave de um provedor e cliente construído com outro.
        self._selecao_autospec = self._resolver_selecao(selecao_resolvida)
        self._validar_chave_do_provedor(
            self._selecao_autospec["provider"], gemini_key, chaves
        )

        # [CP 3.2] LangChain removido -- `self._llm` é um `LLMClient` (via
        # `get_llm`), que já resolve o modelo e a `temperature=0.1` (via
        # `_POLITICA_RETRY_POR_TAREFA["autospec"]` em `core/llm/client.py`).
        self._llm = get_llm(
            "autospec",
            self.gemini_key,
            chaves=chaves,
            selecao_resolvida=self._selecao_autospec,
        )
        self.searcher = WebSearcher(self.google_key, self.cse_id)
        self.pdf_parser = PDFProcessor(self.llama_key)
        # P-04: preenchido por `generate_ai_response` a cada chamada (sempre
        # zerado antes). Vale só para a ÚLTIMA ficha processada -- leia logo
        # depois da chamada, como `process_queue` faz.
        self.ultimas_fontes_por_campo = {}

    @staticmethod
    def _resolver_selecao(selecao_resolvida):
        """Mesma cadeia de `get_llm`: seleção injetada > seleção salva pelo
        usuário no painel "Modelos de IA" > `config.LLM_MODELOS_HOJE`.

        Devolve SEMPRE um dict concreto `{"provider", "model"}` -- nunca
        `None` -- porque o resultado é repassado a `get_llm` como
        `selecao_resolvida`, onde `None` significaria "vá ler o disco de
        novo" e reabriria a janela de divergência que este método fecha.
        """
        if selecao_resolvida is not None:
            return selecao_resolvida

        from sigft.core.llm import selecao  # import local -- mesmo padrão de get_llm

        resolvido = selecao.resolver("autospec", config_path=config.CONFIG_FILE)
        return resolvido if resolvido is not None else config.LLM_MODELOS_HOJE["autospec"]

    @staticmethod
    def _validar_chave_do_provedor(provider_id, gemini_key, chaves):
        """Falha cedo, e com o nome do provedor REALMENTE em uso.

        Antes desta correção o guard era `if not gemini_key: raise
        ValueError("Chave Gemini é obrigatória.")`, escrito quando o módulo
        só sabia falar com o Gemini. Depois do CP 3.2 o AutoSpec roda por
        `LLMClient` e o provedor sai da seleção do usuário -- então quem
        configurava apenas `OPENROUTER_API_KEY` levava um erro pedindo uma
        chave do Gemini que o fluxo nem usaria. Ver
        docs/refatoracao/PENDENCIAS.md (2026-08-11).

        A mensagem é a MESMA para todo provedor, com o provedor e a chave
        esperada interpolados. Nenhum provedor é caso especial no texto --
        decisão de 2026-08-11, olhando para a migração para OpenRouter que
        já está no horizonte: uma mensagem que diz "Gemini" envelhece no dia
        em que o provedor padrão mudar, e ninguém lembra de trocá-la.

        O que continua diferente entre os provedores é só DE ONDE a chave
        vem, não o texto do erro:
          - Gemini: do argumento `gemini_key` (o `frontend.py` passa
            `get_key("GEMINI")`), que `get_llm` usa tal qual;
          - demais: de `config.carregar_chaves()`, pelo nome lógico em
            `config.CHAVE_POR_PROVIDER`.
        """
        nome_chave = config.CHAVE_POR_PROVIDER.get(provider_id)
        if nome_chave is None:
            # Provedor sem chave mapeada: não há o que validar aqui. Deixa
            # seguir para `get_llm`, que levanta o `NotImplementedError` com
            # a lista de provedores suportados -- erro melhor que qualquer
            # um que este guard saberia inventar.
            return

        if provider_id == config.PROVIDER_GEMINI:
            tem_chave = bool(gemini_key)
        else:
            chaves_resolvidas = chaves if chaves is not None else config.carregar_chaves()
            tem_chave = bool(chaves_resolvidas.get(nome_chave))

        if not tem_chave:
            raise ValueError(
                f"O AutoSpec não tem chave de IA configurada para o provedor "
                f"'{provider_id}' (chave esperada: '{nome_chave}'). Configure-a "
                f"na Home, ou escolha no painel 'Modelos de IA' um provedor "
                f"cuja chave você já tenha."
            )

    # P-06: quantas linhas seguidas SEM pergunta encerram a varredura das
    # especificações variáveis. 25 é folgado o suficiente para atravessar um
    # bloco de linhas de layout no meio da lista e curto o suficiente para
    # não varrer planilha formatada até o fim.
    MAX_LINHAS_VAZIAS_SEGUIDAS = 25

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

    @staticmethod
    def _sufixo_pmib_da_celula(valor):
        """Sufixo PMIB canônico da célula (`"0105"`), ou `""` se não houver.

        Existe para que `get_pmib_data` compare sufixo COM sufixo. Até
        2026-08-11 a comparação era `if code_suffix in val_pmib` -- substring
        contra o código inteiro, prefixo de contrato incluído. Como o prefixo
        (`config.PREFIXO_CONTRATO`, hoje `"4500063671"`) contém ele mesmo
        sequências de 4 dígitos, 7 sufixos (`0006`, `0063`, `0636`, `3671`,
        `4500`, `5000`, `6367`) casavam com QUALQUER linha da planilha, e a
        função devolvia a descrição e o código de material da PRIMEIRA linha
        -- de um material completamente diferente. O erro é silencioso e
        contamina o contexto RAG e as queries de busca web, ou seja, a IA
        pesquisa e preenche a ficha com base no material errado. Ver
        docs/refatoracao/PENDENCIAS.md (2026-08-11).

        A normalização passa por `core.excel.pmib_codes` (implementação
        única, CP 1.2), o que de quebra conserta um FALSO NEGATIVO: quando o
        Excel guarda o código como número, `4500063671.1050` vira o float
        `4500063671.105` e a comparação de hoje falha -- `normalize_pmib`
        restaura o zero à direita.
        """
        if valor is None:
            return ""
        texto = str(valor).strip()
        if not texto:
            return ""
        # A célula pode trazer o código no meio de texto livre
        # ("4500063671.0105 - BOMBA"), caso que a substring de antes cobria
        # e que precisa continuar casando.
        completo = pmib_codes.find_pmib_code_in_text(texto)
        norm = pmib_codes.normalize_pmib(completo if completo else valor)
        if not norm:
            return ""
        return norm.split(".")[-1] if "." in norm else norm

    def get_pmib_data(self, pmib_path, code_suffix):
        try:
            wb = openpyxl.load_workbook(pmib_path, data_only=True)
            ws = wb.active
            pmib_col, desc_col, mat_col, start_row = self.find_header_columns(ws)
            if not pmib_col or not desc_col: return "", ""

            for row in ws.iter_rows(min_row=start_row):
                if len(row) < max(pmib_col, desc_col, mat_col): continue
                c_pmib = row[pmib_col-1]

                if self._sufixo_pmib_da_celula(c_pmib.value) == code_suffix:
                    desc_val = str(row[desc_col-1].value).strip() if row[desc_col-1].value else ""
                    mat_val = str(row[mat_col-1].value).strip() if row[mat_col-1].value else ""
                    return desc_val, mat_val
            return "", ""
        except Exception: return "", ""

    def is_empty(self, val):
        s_val = str(val).strip().upper()
        return not val or s_val == "" or s_val.startswith("FORNECER")

    # P-01: alcance da varredura em busca do rótulo de um checkbox.
    ALCANCE_ROTULO_CHECKBOX = 4

    @staticmethod
    def _texto_util_para_rotulo(ws, linha, coluna):
        """Valor de célula que serve como rótulo, ou `None`.

        Descarta o que não é rótulo: célula vazia, a marca `"x"` solta, e
        qualquer célula que seja a MARCAÇÃO de um grupo de checkbox (sem
        isso, varrer à direita de `J69` alcança o `P69` do grupo vizinho e
        devolve `"x"` como se fosse rótulo — erro observado na ficha real).
        """
        if coluna < 1 or linha < 1:
            return None
        cel = ws.cell(row=linha, column=coluna)
        if cel.coordinate in _CELULAS_DE_MARCACAO:
            return None
        valor = cel.value
        if valor in (None, ""):
            return None
        texto = str(valor).strip()
        if not texto or texto.lower() in ("x", "×"):
            return None
        return texto

    @classmethod
    def _rotulos_checkbox_seguro(cls, ws, celulas):
        """`_rotulos_do_checkbox` que nunca levanta. Rótulo é enriquecimento
        opcional -- uma planilha atípica não pode impedir a ficha de ser
        analisada."""
        try:
            return cls._rotulos_do_checkbox(ws, celulas)
        except Exception:
            return {}

    @classmethod
    def _rotulos_do_checkbox(cls, ws, celulas):
        """Mapa `{célula: rótulo legível}` lido da PRÓPRIA planilha.

        O `CONFIG_MAP` guarda só endereços (`['G25','G27','G29']`), e era
        isso que o prompt oferecia à IA — endereços não dizem nada a um
        modelo de linguagem, então mesmo um acerto era chute entre 3
        opções. O rótulo, porém, está na planilha, ao lado da marcação.

        Duas disposições, ambas confirmadas na ficha real 4500063671.0662
        (ver Anexo B de docs/base-conhecimento/08b-autospec-contexto-negocio.md):

          - **à direita, mesma linha** — 7 dos 9 grupos
            (`G27` → `H27` = "Horizontal");
          - **na linha de cabeçalho acima**, varrendo para a esquerda a
            partir da coluna da marca — os 2 grupos da linha 69
            (`E69` → `D68` = "Classe I - Perigoso").

        Célula sem rótulo encontrável simplesmente não entra no mapa; quem
        chama continua tendo o endereço como alternativa.
        """
        rotulos = {}
        for celula in celulas:
            try:
                col = _indice_da_coluna(
                    "".join(c for c in celula if c.isalpha())
                )
                lin = int("".join(c for c in celula if c.isdigit()))
            except (ValueError, TypeError):
                continue

            achado = None
            # A leitura de rótulo é um BÔNUS: se a worksheet não suportar o
            # acesso por `.cell(row=, column=)` (fakes de teste antigos, um
            # objeto duck-typed mais magro), o campo simplesmente segue sem
            # rótulo e `fill_save` continua aceitando o endereço da célula —
            # exatamente o comportamento anterior a esta melhoria. Um extra
            # não pode derrubar a análise da ficha.
            if not hasattr(ws, "cell"):
                return rotulos
            for d in range(1, cls.ALCANCE_ROTULO_CHECKBOX + 1):
                achado = cls._texto_util_para_rotulo(ws, lin, col + d)
                if achado:
                    break
            if not achado:
                for d in range(0, cls.ALCANCE_ROTULO_CHECKBOX + 1):
                    achado = cls._texto_util_para_rotulo(ws, lin - 1, col - d)
                    if achado:
                        break
            if achado:
                rotulos[celula] = achado
        return rotulos

    # --- Análise da Ficha ---
    def analyze_sheet(self, filepath, status_pmib_path):
        # P-07: DUAS aberturas do mesmo arquivo, de propósito.
        #
        # `wb` (sem `data_only`) é o que sai daqui e é salvo por `fill_save`
        # — precisa manter as FÓRMULAS, que `data_only=True` descartaria na
        # gravação. `ws_valores` (com `data_only=True`) é só para LEITURA:
        # sem ele, `is_empty` enxergaria o texto da fórmula (`"=A1"`) e
        # trataria a célula como preenchida quando o valor calculado é
        # vazio. Ler de um e escrever no outro é o que concilia as duas
        # necessidades.
        wb = openpyxl.load_workbook(filepath)
        if "Ficha Técnica Padrão" not in wb.sheetnames:
            raise ValueError("Aba 'Ficha Técnica Padrão' não encontrada.")
        ws_escrita = wb["Ficha Técnica Padrão"]

        try:
            wb_valores = openpyxl.load_workbook(filepath, data_only=True)
            ws = wb_valores["Ficha Técnica Padrão"]
        except Exception:
            # Planilha nunca aberta no Excel não tem valor calculado em
            # cache; nesse caso `data_only=True` devolve `None` em toda
            # célula com fórmula. Cair para a leitura direta é melhor que
            # tratar a ficha inteira como vazia.
            ws = ws_escrita

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
                    missing[key] = {
                        "type": "checkbox",
                        "options": cfg["cells"],
                        "desc": cfg.get("desc", ""),
                        "ref": cfg["cells"],
                        # P-01: rótulos lidos da própria planilha, para o
                        # prompt poder oferecer "Vertical" em vez de "G25".
                        # Best-effort: sem rótulo, cai no endereço de célula.
                        "rotulos": self._rotulos_checkbox_seguro(ws, cfg["cells"]),
                    }

        # Mapeamento Dinâmico (Variáveis)
        #
        # P-06: as regras de negócio dizem "linha 79 até a última linha
        # PREENCHIDA", mas o laço ia até `ws.max_row` -- que no openpyxl conta
        # linha com FORMATAÇÃO, não com conteúdo. Na ficha real
        # 4500063671.0662 as perguntas acabam na linha 103 e `max_row` é 132;
        # num template com estilo aplicado até o fim da planilha isso vira
        # dezenas de milhares de iterações inúteis por ficha.
        #
        # Para parar sem arriscar perder pergunta depois de um buraco, exige
        # uma SEQUÊNCIA de linhas sem pergunta (as fichas numeram as
        # perguntas em ordem — "1 - APLICACAO", "2 - MATERIAL" ... —, então
        # um vão maior que isso significa fim da lista, não lacuna).
        r = VARIAVEIS_SPECS["start_row"]
        vazias_seguidas = 0
        while r <= ws.max_row and vazias_seguidas < self.MAX_LINHAS_VAZIAS_SEGUIDAS:
            p_val = ws.cell(row=r, column=VARIAVEIS_SPECS["pergunta_col_idx"]).value
            r_val = ws.cell(row=r, column=VARIAVEIS_SPECS["resposta_col_idx"]).value
            if p_val:
                vazias_seguidas = 0
                if self.is_empty(r_val):
                    clean_p = str(p_val).strip().replace(":", "")
                    missing[f"var_row_{r}"] = {"type": "text", "desc": clean_p, "ref": ws.cell(row=r, column=VARIAVEIS_SPECS["resposta_col_idx"]).coordinate}
            else:
                vazias_seguidas += 1
            r += 1

        return wb, missing, txt_brv, fab, desc_comp, cod_mat

    # --- RAG: Busca e Contexto ---
    # Piso do truncamento progressivo (passo 3 da cascata): abaixo disso a
    # query vira genérica demais para valer a chamada -- "CONJUNTO Hydac
    # datasheet specs" traz catálogo de qualquer coisa.
    MIN_TOKENS_BUSCA = 2

    @classmethod
    def _montar_queries_busca(cls, txt_brv, fab, cod_mat):
        """Cascata de busca web, do mais específico ao mais genérico
        (regras de negócio §4.2).

        1. `"{cod_mat}" {fab} datasheet specs` -- aspas = busca exata;
        2. `{txt_brv} {fab} datasheet specs`;
        3. o mesmo, largando **a última PALAVRA** do `txt_brv` a cada
           rodada, até sobrarem `MIN_TOKENS_BUSCA` tokens.

        O passo 3 estava descrito nas regras de negócio e não existia no
        código até 2026-08-11 -- descrições longas e específicas ("CONJUNTO
        REPARO PARA BOMBA 3527528 PVF100-4 NBR") não retornam nada no
        Google, e a ficha ficava sem contexto web nenhum.

        Corta por PALAVRA, não pelos 4 caracteres que o texto original das
        regras sugeria: cortar por caractere parte o token no meio
        ("PVF100-4" -> "PVF10") e produz query pior que a anterior. O
        fabricante fica SEMPRE na query -- é ele que ancora o filtro
        anti-intruso (§4.3).

        Devolve lista sem repetição, preservando a ordem.
        """
        # O texto vem da planilha e costuma trazer espaço duplo e sobra no
        # fim (visto na ficha real 4500063671.0662): `.split()` normaliza.
        tokens = str(txt_brv or "").split()
        fab_txt = str(fab or "").strip()

        queries = []
        if cod_mat:
            queries.append(f'"{cod_mat}" {fab_txt} datasheet specs'.strip())

        for corte in range(len(tokens), cls.MIN_TOKENS_BUSCA - 1, -1):
            if corte <= 0:
                break
            trecho = " ".join(tokens[:corte])
            queries.append(f"{trecho} {fab_txt} datasheet specs".strip())

        vistas = set()
        unicas = []
        for q in queries:
            if q not in vistas:
                vistas.add(q)
                unicas.append(q)
        return unicas

    def retrieve_context(self, txt_brv, fab, cod_mat, refs_locais, callbacks=None):
        cb = callbacks or _callbacks_silenciosos()

        # 1. Processar Locais
        local_txt = self.process_local_documents(refs_locais, callbacks=cb)

        # 2. Busca Web
        web_txt = ""
        sources = []

        if not (self.google_key and self.cse_id):
            cb.log(
                "Busca web desativada (chave do Google Search ou CSE ID ausente) "
                "— o contexto virá só dos documentos locais.",
                nivel="warn",
            )
            return (local_txt + "\n\n" + web_txt), sources

        required = []
        if fab and len(fab) > 2: required.append(fab)
        if cod_mat and len(cod_mat) > 2: required.append(cod_mat)

        queries = self._montar_queries_busca(txt_brv, fab, cod_mat)

        for i, q in enumerate(queries, start=1):
            files = self.searcher.search_and_download(
                q, required_terms=required, max_results=3, callbacks=cb
            )
            if not files:
                cb.log(f"Busca {i}/{len(queries)} sem resultado util: {q}", nivel="info")
                continue

            aproveitados = 0
            for item in files:
                t, m = self.pdf_parser.extract_text(item['path'], callbacks=cb)
                if t and len(t) > 100:
                    web_txt += f"--- WEB DOC: {item['title']} ---\nURL: {item['url']}\n{t[:50000]}\n\n"
                    sources.append(item['url'])
                    aproveitados += 1
                    cb.log(f"Documento web aproveitado ({m}, {len(t)} chars): {item['url']}")
                else:
                    cb.log(
                        f"Documento web descartado (texto insuficiente): {item['url']}",
                        nivel="warn",
                    )
                try: os.remove(item['path'])
                except Exception: pass

            # Só encerra a cascata se algum documento REALMENTE virou
            # contexto. Antes bastava a busca devolver arquivos: 3 PDFs
            # ilegíveis paravam a cascata e a ficha seguia sem contexto web,
            # com as queries mais genéricas nunca tentadas.
            if aproveitados:
                cb.log(f"Busca {i}/{len(queries)} rendeu {aproveitados} documento(s): {q}")
                break
            cb.log(
                f"Busca {i}/{len(queries)} achou {len(files)} arquivo(s), nenhum legivel "
                f"— seguindo para a proxima query.",
                nivel="warn",
            )

        if not sources:
            cb.log(
                f"Nenhum documento web aproveitavel apos {len(queries)} tentativa(s). "
                f"O contexto virá só dos documentos locais.",
                nivel="warn",
            )

        return (local_txt + "\n\n" + web_txt), sources

    def process_local_documents(self, paths, callbacks=None):
        cb = callbacks or _callbacks_silenciosos()
        ctx = []
        for p in paths:
            nome = os.path.basename(str(p))
            try:
                t, m = self.pdf_parser.extract_text(p, callbacks=cb)
                if t:
                    ctx.append(f"--- LOCAL DOC: {nome} ---\n{t[:60000]}")
                    cb.log(f"Manual local lido ({m}, {len(t)} chars): {nome}")
                else:
                    cb.log(
                        f"Manual local nao rendeu texto: {nome} — nao entra no contexto.",
                        nivel="warn",
                    )
            except Exception as e:
                cb.log(
                    f"Falha ao processar manual local {nome} ({type(e).__name__}: {e}).",
                    nivel="error",
                )
        return "\n\n".join(ctx)

    # --- Geração IA ---
    def generate_ai_response(self, txt_brv, fab, desc_comp, missing, context, callbacks=None):
        cb = callbacks or _callbacks_silenciosos()
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
            if v['type'] == 'checkbox':
                # P-01: oferece os RÓTULOS legíveis quando a planilha os
                # tiver. Antes ia `(Opções: ['G25','G27','G29'])` — endereços
                # de célula, que não significam nada para um modelo de
                # linguagem: mesmo um acerto era chute entre 3. Com rótulo, a
                # pergunta vira respondível ("Vertical/Horizontal/
                # Indiferente"), e `fill_save` traduz de volta para a célula.
                rotulos = v.get('rotulos') or {}
                legiveis = [rotulos.get(c) for c in v['options'] if rotulos.get(c)]
                if len(legiveis) == len(v['options']):
                    info += f" (Escolha UMA: {legiveis})"
                else:
                    info += f" (Opções: {v['options']})"
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
            return self._normalizar_resposta_ia(resp.parsed_json)
        except Exception as e:
            # Até 2026-08-11 isto era `print(f"Erro IA: {e}")` -- ia para o
            # stdout, ou seja, a janela preta que ninguém olha. O CP 4.4
            # padronizou os logs pelo console da UI e este ponto ficou de
            # fora: a ficha voltava vazia sem nenhuma explicação visível.
            cb.log(f"Chamada de IA falhou ({type(e).__name__}: {e}).", nivel="error")
            return {}

    def _normalizar_resposta_ia(self, parsed):
        """Achata a resposta da IA para `{campo: valor}` e guarda as fontes
        em `self.ultimas_fontes_por_campo`.

        **Aceita as DUAS formas de propósito** (P-04, 2026-08-11):

          - `{"campo": "valor"}` — a forma de antes. Continua valendo, e é
            o que um modelo mais fraco devolve mesmo com a instrução nova
            no prompt;
          - `{"campo": {"valor": ..., "fonte": ...}}` — a forma que o
            prompt passou a pedir.

        Tolerar as duas é o que impede que a rastreabilidade vire uma
        regressão: se o modelo ignorar a instrução 7, o preenchimento
        continua funcionando exatamente como antes, só sem a fonte. O
        contrato de RETORNO não mudou — `fill_save` recebe o mesmo
        `{campo: valor}` de sempre.
        """
        self.ultimas_fontes_por_campo = {}
        if not isinstance(parsed, dict):
            return parsed

        achatado = {}
        for campo, bruto in parsed.items():
            if isinstance(bruto, dict) and "valor" in bruto:
                achatado[campo] = bruto.get("valor")
                fonte = bruto.get("fonte")
                if fonte:
                    self.ultimas_fontes_por_campo[campo] = str(fonte)
            else:
                achatado[campo] = bruto
        return achatado

    @staticmethod
    def _resolver_celula_checkbox(resposta, info):
        """Traduz a resposta da IA para a CÉLULA que deve receber o "X".

        Aceita, nesta ordem:
          1. o **endereço** da célula (`"G25"`, `"g25"`) — a única forma que
             funcionava antes de 2026-08-11, preservada;
          2. o **rótulo** lido da planilha (`"Horizontal"`, `"NAO REPARAVEL"`)
             — comparação sem acento e sem caixa;
          3. rótulo **contido** na resposta, ou vice-versa, para o caso de o
             modelo responder por extenso ("Armazenar na posição horizontal")
             — só quando um ÚNICO rótulo casa, para não escolher no chute.

        Devolve `None` quando nada casa; quem chama registra o descarte.
        """
        opcoes = info.get('options') or []
        rotulos = info.get('rotulos') or {}
        if resposta is None:
            return None

        bruto = str(resposta).strip()
        if not bruto:
            return None

        # 1. endereço de célula
        if bruto.upper() in opcoes:
            return bruto.upper()

        chave = _chave_comparacao(bruto)
        if not chave:
            return None

        # 2. rótulo exato (normalizado)
        for celula in opcoes:
            if celula in rotulos and _chave_comparacao(rotulos[celula]) == chave:
                return celula

        # 3. contenção, só se for inequívoca
        candidatos = []
        for celula in opcoes:
            rotulo = rotulos.get(celula)
            if not rotulo:
                continue
            chave_rotulo = _chave_comparacao(rotulo)
            if not chave_rotulo:
                continue
            if chave_rotulo in chave or chave in chave_rotulo:
                candidatos.append(celula)
        return candidatos[0] if len(candidatos) == 1 else None

    def fill_save(self, wb, filepath, ai_data, missing, callbacks=None):
        cb = callbacks or _callbacks_silenciosos()
        ws = wb["Ficha Técnica Padrão"]
        font = Font(color="0000FF")
        nao_casados = []

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
                    alvo = self._resolver_celula_checkbox(val, info)
                    if alvo:
                        for o in info['options']: ws[o].value = None
                        ws[alvo].value = "X"
                        ws[alvo].font = font
                    else:
                        # P-01: antes o `else` não existia — resposta fora das
                        # opções era descartada em SILÊNCIO e a ficha voltava
                        # com o campo vazio, sem nada indicando que a IA havia
                        # respondido. Falhar calado é pior que falhar.
                        cb.log(
                            f"Checkbox '{k}': resposta {str(val)!r} não casou com "
                            f"nenhuma opção {info['options']} — campo deixado em "
                            f"branco para preenchimento manual.",
                            nivel="warn",
                        )
                        nao_casados.append(k)

        if nao_casados:
            cb.log(
                f"{len(nao_casados)} checkbox(es) ficaram em branco por resposta "
                f"nao reconhecida: {', '.join(nao_casados)}.",
                nivel="warn",
            )

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
                    full_ctx, sources = self.retrieve_context(
                        txt, fab, cod, refs, callbacks=callbacks
                    )
                    yield from _flush()
                    if sources: yield f" -> Fontes Web: {len(sources)}"

                    # 3. IA
                    # Nada de citar provedor aqui: o modelo vem de
                    # `config.LLM_TASKS`/seleção da UI e pode ser OpenRouter
                    # ou o endpoint da empresa. Mensagem que nomeia "Gemini"
                    # envelhece igual à do guard de chave.
                    yield " -> Consultando a IA..."
                    ai_resp = self.generate_ai_response(
                        txt, fab, desc, missing, full_ctx, callbacks=callbacks
                    )
                    yield from _flush()

                    # P-04: rastreabilidade campo->fonte. As regras de negócio
                    # (§3.4) pedem que o engenheiro veja de onde saiu cada
                    # dado antes de homologar; até aqui ele via só a lista de
                    # fontes do lote.
                    fontes = getattr(self, "ultimas_fontes_por_campo", {}) or {}
                    if fontes:
                        yield f" -> Origem dos dados ({len(fontes)} campo(s)):"
                        for campo, fonte in fontes.items():
                            yield f"      · {campo}: {fonte}"
                    elif ai_resp:
                        yield (
                            "      (a IA não informou a origem dos dados — "
                            "confira manualmente antes de homologar)"
                        )

                    # 4. Salvar
                    out_path = self.fill_save(wb, ficha, ai_resp, missing, callbacks=callbacks)
                    yield f" -> Salvo: {os.path.basename(out_path)}"
                    lote.sucesso(fname, f"salvo como {os.path.basename(out_path)}")
                    yield from _flush()

                except Exception as e:
                    yield f" -> ERRO: {e}"
                    lote.falha(fname, f"{type(e).__name__}: {e}")
                    yield from _flush()

        yield from _flush()
