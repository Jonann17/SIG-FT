import os
import openpyxl
import shutil
from openpyxl.styles import Font
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont

from sigft import config
from sigft.core.excel import headers, pmib_codes
from sigft.core.rpa.ficha_layout import (
    CONFIG_MAP,
    MAX_LINHAS_VAZIAS_SEGUIDAS,
    VARIAVEIS_SPECS,
)
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
from sigft.services import analyzer_relatorio

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


# Terceiro destino, ao lado de FT_good/FT_bad (decisao do usuario, 2026-08-26).
#
# NAO e "ficha ruim" -- e ficha que o aplicativo NAO CONSEGUIU analisar, e que
# por isso nao pode receber nota nenhuma. Duas situacoes caem aqui:
#
#   1. a secao de caracteristicas tecnicas nao existe na ficha. Ela TEM de
#      existir; sem ela nao ha o que pontuar, e a ficha volta para o
#      fornecedor preencher antes de qualquer analise;
#   2. a IA nao respondeu (chave, cota, rede). Sem o julgamento dela a nota
#      sairia inflada.
#
# Nos dois casos o que vai para a pasta e o arquivo ORIGINAL, sem marcacao e
# sem porcentagem no nome: nota que nao existe nao pode aparecer no nome do
# arquivo que o fornecedor vai receber.
PASTA_NAO_CONCLUIDAS = "FT_nao_concluidas"


def aba_do_status_pmib(wb):
    """A aba do `_STATUS_PMIB` que tem os cabeçalhos, não a que estava
    selecionada quando o arquivo foi salvo.

    Mesmo bug do `wb.active` da ficha, do outro lado do fluxo: com a aba
    errada, `_find_header_columns` não acha as colunas e **todas** as fichas
    do lote perdem o enriquecimento de descrição, cada uma com um
    `[AVISO] PMIB não encontrado` que parece defeito da planilha do usuário.

    Sem cabeçalho em aba nenhuma, devolve `wb.active` — o comportamento de
    hoje. Vive no serviço, e não na tela, porque é regra de negócio
    (princípio nº 2 da arquitetura).
    """
    try:
        abas = list(wb.worksheets)
    except Exception:
        return wb.active
    if len(abas) <= 1:
        return abas[0] if abas else wb.active

    for ws in abas:
        try:
            linhas = headers.rows_from_worksheet(ws, max_row=10)
            _, linha_cabecalho = headers.find_columns(
                linhas,
                {config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
                 config.COL_DESCRICAO: config.COL_DESCRICAO},
            )
        except Exception:
            continue
        if linha_cabecalho is not None:
            return ws
    return wb.active


def nome_com_a_nota(nome_original, nota):
    """`4500063671.0071.xlsx` + 87 -> `4500063671.0071_87%.xlsx`.

    Era `nome.replace(".xlsx", f"_{nota}%.xlsx")`, e `str.replace` troca
    TODAS as ocorrências: `ficha.xlsx.revisao.xlsx` saía como
    `ficha_87%.xlsx.revisao_87%.xlsx` (medido em 2026-08-26). Só a extensão
    final é extensão.
    """
    base, ponto, extensao = str(nome_original).rpartition(".")
    if ponto and extensao.lower() == "xlsx":
        return f"{base}_{nota}%.xlsx"
    return f"{nome_original}_{nota}%.xlsx"


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
        # Motivo da última falha de IA. Existe porque o `print` de
        # `_call_gemini_api` ia para a janela preta -- que no app empacotado
        # não tem para onde ir. `processar_planilha` publica isto no log da
        # tela, junto do aviso de nota inflada.
        self.ultimo_erro_ia = None

    # -----------------------------------------------------------------
    # LEITURA DA PLANILHA
    # -----------------------------------------------------------------
    def _aba_da_ficha(self, wb):
        """A aba que de fato contém a ficha, e não a que estava selecionada
        quando o arquivo foi salvo.

        **O bug que isto conserta**, medido em 2026-08-26 com `.xlsx` real: a
        MESMA ficha caía de **100% para 0%** quando o usuário salvava o
        arquivo com outra aba em primeiro plano. `wb.active` devolvia a aba
        errada, todo campo obrigatório era lido como vazio, cada um recebia
        'FORNECER' numa aba que não é a ficha, e o arquivo ia para `FT_bad`.

        A escolha é por evidência, não por nome de aba: conta quantas âncoras
        do `CONFIG_MAP` estão preenchidas e se o título das especificações
        aparece. **Empate ou nenhum sinal -> `wb.active`**, o comportamento de
        sempre — este método só pode melhorar o resultado, nunca piorar.
        """
        try:
            abas = list(wb.worksheets)
        except Exception:
            return wb.active
        if len(abas) <= 1:
            return abas[0] if abas else wb.active

        try:
            ativa = wb.active
        except Exception:
            ativa = abas[0]

        melhor, melhor_nota = ativa, self._quanto_parece_ficha(ativa)
        for ws in abas:
            if ws is ativa:
                continue
            nota = self._quanto_parece_ficha(ws)
            if nota > melhor_nota:  # `>` e não `>=`: empate fica com a ativa
                melhor, melhor_nota = ws, nota
        return melhor if melhor_nota > 0 else ativa

    def _quanto_parece_ficha(self, ws):
        """Quantas evidências de que esta aba é a ficha. 0 = nenhuma."""
        pontos = 0
        for cfg in CONFIG_MAP.values():
            try:
                if cfg["type"] == "cell":
                    alvo = cfg["range"].split(":")[0]
                else:
                    alvo = cfg["cells"][0]
                if ws[alvo].value not in (None, ""):
                    pontos += 1
            except Exception:
                continue
        return pontos


    def _registrar_no_relatorio(self, codigo_pmib, original_filename, nota, achados):
        """Publica os achados desta ficha, SE a tela tiver ligado o relatório.

        Opcional de propósito: quem não liga (testes antigos, uso por script)
        não pode quebrar, e o `getattr` faz isso valer também para instâncias
        criadas com `__new__`, que e o idioma dos testes deste repositorio.
        """
        relatorio = getattr(self, "relatorio", None)
        if relatorio is None:
            return
        try:
            # Codigo COMPLETO (`4500063671.0071`), nao o sufixo de 4 digitos
            # que o resto do analyzer usa para casar linha na planilha: quem
            # recebe o relatorio precisa achar o material, e `0071` sozinho so
            # identifica dentro do contrato.
            completo = pmib_codes.extract_pmib_code_full(str(original_filename or ""))
            relatorio.registrar(completo or codigo_pmib, original_filename, nota, achados)
        except Exception:
            pass  # relatorio e conforto; nunca pode derrubar a analise

    def _guardar_nao_concluida(self, input_filepath, root_output_dir,
                               subfolder_name, original_filename):
        """Copia o ORIGINAL para `FT_nao_concluidas/`. Devolve o caminho, ou
        uma string de erro começada por `ERRO:`."""
        destino = os.path.join(root_output_dir, PASTA_NAO_CONCLUIDAS, subfolder_name)
        try:
            os.makedirs(destino, exist_ok=True)
            caminho = os.path.join(destino, original_filename)
            shutil.copy2(input_filepath, caminho)
            return caminho
        except Exception as e:
            return f"ERRO: {e}"

    def _aba_de_valores(self, caminho, ws_gravavel):
        """A mesma aba, aberta com `data_only=True` — valores calculados no
        lugar do texto das fórmulas.

        Qualquer problema devolve a própria aba gravável: a leitura dupla é
        uma melhora, e uma melhora não pode ser motivo de falha.
        """
        try:
            wb = openpyxl.load_workbook(caminho, data_only=True)
        except Exception:
            return ws_gravavel
        titulo = getattr(ws_gravavel, "title", None)
        try:
            for aba in wb.worksheets:
                if getattr(aba, "title", None) == titulo:
                    return aba
            return wb.active
        except Exception:
            return ws_gravavel

    def _valor_calculado(self, ws_valores, ws, ref, formulas_sem_valor):
        """O valor da célula como o Excel o mostra.

        **A armadilha do `data_only`:** ele devolve o valor em CACHE, e ficha
        nunca aberta no Excel não tem cache — a fórmula existe e o valor é
        `None`. Tratar isso como célula vazia escreveria 'FORNECER' por cima
        de uma fórmula que o usuário escreveu, o que é pior que o problema
        original. Nesse caso o comportamento de hoje é mantido (o texto cru)
        e o campo entra em `formulas_sem_valor`, que vira aviso no console.
        """
        bruto = ws[ref].value
        if ws_valores is ws:
            return bruto
        try:
            calculado = ws_valores[ref].value
        except Exception:
            return bruto
        if calculado is None and isinstance(bruto, str) and bruto.startswith("="):
            formulas_sem_valor.append(ref)
            return bruto
        return calculado

    def _ler_specs(self, ws, linha_inicial, ws_valores=None):
        """As especificações técnicas, da `linha_inicial` até o fim da lista.

        **O bug que isto conserta**, medido em 2026-08-26: o laço antigo era
        `if not p_val: break`, então **uma linha de respiro no meio da lista
        encerrava a leitura**. Uma ficha com 5 perguntas em 6 linhas tinha 2
        analisadas — e as outras 3 sumiam da nota sem nenhum aviso.

        Pior: como os pontos por spec são `max_variable_points / total`, a
        ficha truncada dava **mais pontos por spec** que a completa. Um
        buraco na planilha deixava a ficha mais fácil de aprovar.

        A lista acaba de verdade depois de `MAX_LINHAS_VAZIAS_SEGUIDAS`
        (`ficha_layout`) perguntas em branco — mesma regra do autospec.
        Pergunta sem resposta CONTINUA na lista: apontar isso é o serviço.
        """
        col_p = VARIAVEIS_SPECS["pergunta_range"].split(':')[0]
        col_r = VARIAVEIS_SPECS["resposta_range"].split(':')[0]
        specs = []
        vazias_seguidas = 0
        linha = linha_inicial
        while vazias_seguidas < MAX_LINHAS_VAZIAS_SEGUIDAS:
            pergunta = ws[f"{col_p}{linha}"].value
            if not pergunta:
                vazias_seguidas += 1
                linha += 1
                continue
            vazias_seguidas = 0
            # A célula vem da aba GRAVÁVEL (é nela que 'FORNECER' será
            # escrito); a resposta, da aba de valores.
            celula = ws[f"{col_r}{linha}"]
            fonte = ws_valores if ws_valores is not None else ws
            specs.append({"pergunta": pergunta,
                          "resposta": fonte[f"{col_r}{linha}"].value,
                          "cell": celula})
            linha += 1
        return specs

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
            # 2026-08-26: era `wb.active`, e a aba ativa é a que estava
            # selecionada quando o arquivo foi salvo -- não necessariamente a
            # ficha. Ver `_aba_da_ficha`: a mesma ficha valia 100% ou 0%
            # dependendo disso.
            ws = self._aba_da_ficha(wb)
            if ws is not wb.active:
                yield f"[INFO] Lendo a aba '{getattr(ws, 'title', '?')}' (a aba ativa nao e a da ficha)."
            # DOIS workbooks de propósito (decisão do usuário, 2026-08-26):
            # `ws` é o GRAVÁVEL (guarda a fórmula, recebe o 'FORNECER' e é o
            # que vai para o disco); `ws_valores` traz o valor CALCULADO.
            # Antes havia um só, sem `data_only`, e uma célula com `=1+1`
            # contava como preenchida enquanto a IA recebia a string '=1+1'
            # como valor do campo (medido).
            ws_valores = self._aba_de_valores(input_filepath, ws)
        except Exception as e:
            yield f"[ERRO] Não foi possível abrir o arquivo. Erro: {e}"
            return False
        formulas_sem_valor = []

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

        # Campos OBRIGATÓRIOS que falharam (lista do usuário, 2026-08-26).
        # Ver a decisão logo antes do salvamento: nota alta não compra campo
        # obrigatório faltando.
        obrigatorios_faltando = []
        # Achados para o relatorio que vai ao FORNECEDOR (2026-08-26). Sao
        # acumulados sempre, de graca; so viram arquivo se a tela tiver ligado
        # `self.relatorio` -- ver `analyzer_relatorio.RelatorioAnalise`.
        achados = []

        # Campos cujo achado NAO e "em branco" e sim "preenchido de forma que
        # nao serve" -- hoje so o "Nao aplicavel" onde ele nao e aceito.
        motivo_do_achado = {}

        # 3. Validação de Campos Fixos (CONFIG_MAP)
        # [CP 8.1] `config` renomeado para `regra`: o nome do laco sombreava
        # o modulo `sigft.config`, importado no topo deste arquivo. Dentro do
        # laco era proposital, mas qualquer uso de `config.X` acrescentado
        # depois pegaria silenciosamente o dicionario da ultima iteracao.
        for key, regra in CONFIG_MAP.items():
            is_valid = True

            # --- Lógica de Pesos Customizados ---
            weight = regra["weight"]
            if custom_weights and key in custom_weights:
                try:
                    weight = float(custom_weights[key])
                except ValueError:
                    pass

            # [ALTERAÇÃO 1] Acumula o peso possível total (para o denominador da normalização)
            total_possible_fixed += weight
            # -----------------------------------------------

            # --- TIPO: CÉLULA ÚNICA ---
            if regra["type"] == "cell":
                # `cell` é da aba gravável (recebe a marcação); o VALOR vem da
                # aba de valores calculados. Ver `_valor_calculado`.
                cell = self.get_cell_from_range(ws, regra["range"])
                val = self._valor_calculado(
                    ws_valores, ws, regra["range"].split(':')[0], formulas_sem_valor)
                val_str = str(val).strip().lower() if val is not None else ""

                if regra["validation"] == "ai":
                    celulas_ai_map[key] = {'cell': cell, 'weight': weight}

                    # `aceita_nao_aplicavel` (2026-08-26): três campos --
                    # içagem, métodos de limpeza e ferramentas de preservação
                    # -- podem legitimamente ser "Não aplicável", e o usuário
                    # confirmou isso campo a campo.
                    #
                    # A contradição que isto conserta: a REGRA 2 do próprio
                    # prompt (`montar_validar_ficha`) já dizia que "Não
                    # aplicável" pode ser VÁLIDO quando a pergunta de fato não
                    # se aplica ao material -- e `FORBIDDEN_NA_STRINGS` matava
                    # a resposta aqui, antes de a IA chegar a vê-la. O código
                    # contrariava o texto que ele mesmo manda para a IA.
                    if regra.get("aceita_nao_aplicavel") and val_str in FORBIDDEN_NA_STRINGS:
                        dados_ia_validar[key] = val
                    elif val_str in FORBIDDEN_NA_STRINGS:
                        self.set_invalid_error(cell, val)
                        is_valid = False
                        motivo_do_achado[key] = "invalido"
                    elif val is None or val_str == "":
                        self.set_blank_error(cell)
                        is_valid = False
                    else:
                        dados_ia_validar[key] = val

                elif key in ["texto_breve_material", "fabricante"]:
                    dados_ia_contexto[key] = val
                    if regra["validation"] == "simple":
                        if val is None or val_str == "":
                            self.set_blank_error(cell)
                            is_valid = False

                elif regra["validation"] == "simple":
                    if val is None or val_str == "":
                        self.set_blank_error(cell)
                        is_valid = False

            # --- TIPO: CHECKBOX ---
            elif regra["type"] == "checkbox":
                is_checked = any(
                    self._valor_calculado(ws_valores, ws, c, formulas_sem_valor) is not None
                    for c in regra["cells"])

                if not is_checked:
                    is_valid = False
                    targets = regra.get("error_target")
                    if targets:
                        if isinstance(targets, list):
                            for t in targets: self.set_blank_error(ws[t])
                        else:
                            self.set_blank_error(ws[targets])
                    else:
                        self.set_blank_error(ws[regra["cells"][0]])

            # Soma pontos GANHOS se passou na validação simples
            if regra.get("validation") == "simple" or regra.get("type") == "checkbox":
                if is_valid:
                    total_score_earned += weight

            if not is_valid:
                achados.append(analyzer_relatorio.Achado(
                    key, motivo_do_achado.get(key, "vazio"),
                    motivo=None, obrigatorio=bool(regra.get("obrigatorio"))))
            if regra.get("obrigatorio") and not is_valid:
                obrigatorios_faltando.append(key)

        # Aplica Descrição Complementar
        if desc_complementar:
            orig = dados_ia_contexto.get("texto_breve_material", "")
            dados_ia_contexto["texto_breve_material"] = f"{orig} ({desc_complementar})" if orig else desc_complementar

        # 4. Mapeamento Dinâmico (Variáveis)
        start_row = self._find_variable_specs_start_row(ws)

        # 4a. Ler a lista INTEIRA numa passada só.
        # Eram dois laços (contar, depois ler) que precisavam concordar, e os
        # dois paravam na primeira linha em branco. Ver `_ler_specs`: uma
        # linha de respiro no meio escondia o resto da lista da nota.
        specs = self._ler_specs(ws, start_row, ws_valores)
        total_vars = len(specs)

        # Usa o max_variable_points passado no argumento
        points_per_var = (max_variable_points / total_vars) if total_vars > 0 else 0
        yield f"[INFO] {total_vars} variáveis encontradas. ({points_per_var:.2f} pts/cada)"

        # SEM ESPECIFICAÇÕES TÉCNICAS a ficha não é analisável (regra de
        # negócio do usuário, 2026-08-26). Esta seção TEM de existir; sem ela
        # não há o que pontuar, e dar nota seria dizer que a ficha foi
        # avaliada quando metade dela nem estava lá.
        #
        # Isto SUBSTITUI a renormalização decidida horas antes (calcular a
        # nota só sobre os campos fixos): o caso não era "pontuar o que
        # existe", era "esta ficha ainda não está pronta para ser analisada".
        if total_vars == 0:
            yield "=" * 60
            yield "⚠️  Ficha SEM a secao de especificacoes tecnicas — NAO ANALISADA."
            yield "   Essa secao e obrigatoria: sem ela nao ha caracteristicas"
            yield "   para avaliar, e dar nota seria avaliar meia ficha."
            yield "   A ficha precisa ser corrigida e reenviada ao FORNECEDOR"
            yield "   para preenchimento antes de passar pelo aplicativo."
            destino = self._guardar_nao_concluida(
                input_filepath, root_output_dir, subfolder_name, original_filename)
            if destino.startswith("ERRO:"):
                yield f"   [ERRO] Nao consegui guardar em {PASTA_NAO_CONCLUIDAS}: {destino[5:]}"
            else:
                yield f"   Guardada em {PASTA_NAO_CONCLUIDAS}/: {os.path.basename(destino)}"
            self._registrar_no_relatorio(
                codigo_pmib_4, original_filename, None,
                [analyzer_relatorio.Achado(
                    "", "nao_analisada",
                    motivo=("A ficha nao tem a secao de ESPECIFICACOES TECNICAS, "
                            "que e obrigatoria. Preencha as caracteristicas tecnicas "
                            "do material e reenvie a ficha."))])
            yield "=" * 60
            return False

        if formulas_sem_valor:
            yield (f"[AVISO] {len(formulas_sem_valor)} celula(s) com FORMULA sem valor "
                   f"calculado ({', '.join(formulas_sem_valor[:6])}). Abra a ficha no "
                   "Excel e salve para o valor ser gravado; ate la o texto da formula "
                   "e o que vai para a analise.")

        # 4b. Validar as respostas
        vars_para_ia = []
        vars_map = []

        for spec in specs:
            r_cell = spec["cell"]
            r_val = spec["resposta"]
            r_str = str(r_val).strip().lower() if r_val is not None else ""

            if r_val is None or r_str == "":
                self.set_blank_error(r_cell)
                achados.append(analyzer_relatorio.Achado(
                    spec["pergunta"], "vazio", especificacao=True))
            else:
                vars_para_ia.append({"pergunta": spec["pergunta"], "resposta": r_val})
                vars_map.append({'cell': r_cell, 'weight': points_per_var,
                                 'pergunta': spec["pergunta"]})

        # 5. Validação Semântica (IA)
        ai_res = None
        ia_foi_consultada = False
        if (dados_ia_validar or vars_para_ia):
            yield "Processando dados..."
            prompt = self._build_gemini_prompt(dados_ia_contexto, dados_ia_validar, vars_para_ia)
            ai_res = self._call_gemini_api(prompt)
            ia_foi_consultada = True
        else:
            yield "Nada para validar via IA."

        # 6. Processar Retorno IA
        ai_valid_fixed = {k: True for k in dados_ia_validar}
        ai_valid_vars = [True] * len(vars_para_ia)

        # `ia_foi_consultada` (2026-08-26): `ai_res` nasce None, então o
        # `if not ai_res` sozinho disparava o alarme de nota inflada TAMBÉM
        # na ficha que não tinha nada para a IA validar -- ou seja, um susto
        # falso justamente na ficha mais bem preenchida.
        if ia_foi_consultada and not ai_res:
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
            yield "⚠️  A IA NÃO respondeu para esta ficha — ficha PULADA."
            # `getattr` e não `self.ultimo_erro_ia` direto: o repositório
            # constrói o analyzer com `DatasheetAnalyzer.__new__(...)` em
            # vários testes (ver test_ficha_layout.py), sem passar pelo
            # `__init__` -- e o acesso direto rebentava com AttributeError no
            # MEIO do processamento, com a ficha já marcada.
            motivo = getattr(self, "ultimo_erro_ia", None)
            if motivo:
                yield f"   Motivo: {motivo}"
            yield "   Sem o julgamento da IA os campos que ela deveria avaliar"
            yield "   contariam como VÁLIDOS, a nota sairia INFLADA, e um arquivo"
            yield "   com nota que não vale é pior que arquivo nenhum."
            destino = self._guardar_nao_concluida(
                input_filepath, root_output_dir, subfolder_name, original_filename)
            if destino.startswith("ERRO:"):
                yield f"   [ERRO] Nao consegui guardar em {PASTA_NAO_CONCLUIDAS}: {destino[5:]}"
            else:
                yield f"   Guardada em {PASTA_NAO_CONCLUIDAS}/: {os.path.basename(destino)}"
            yield "   Confira o log de IA (logs/llm_usage.jsonl) e rode de novo."
            self._registrar_no_relatorio(
                codigo_pmib_4, original_filename, None,
                [analyzer_relatorio.Achado(
                    "", "nao_analisada",
                    motivo=("A analise nao pôde ser concluida: a IA nao respondeu. "
                            "Esta ficha precisa ser processada de novo."))])
            yield "=" * 60
            return False

        if ai_res:
            yield "Aplicando retorno do processamento..."

            # Fixos
            for key, res in ai_res.get("campos_fixos", {}).items():
                if res.get("status") == "INVALIDO":
                    ai_valid_fixed[key] = False
                    c_obj = celulas_ai_map.get(key, {}).get('cell')
                    if c_obj: self.set_invalid_error(c_obj, c_obj.value)
                    # Obrigatório reprovado PELA IA conta igual a obrigatório
                    # em branco: a ficha não pode ser aprovada.
                    achados.append(analyzer_relatorio.Achado(
                        key, "invalido", motivo=res.get("motivo"),
                        obrigatorio=bool(CONFIG_MAP.get(key, {}).get("obrigatorio"))))
                    if CONFIG_MAP.get(key, {}).get("obrigatorio"):
                        obrigatorios_faltando.append(key)

            # Variáveis
            v_results = ai_res.get("campos_variaveis", [])
            for idx, res in enumerate(v_results):
                if res.get("status") == "INVALIDO":
                    if idx < len(vars_map):
                        ai_valid_vars[idx] = False
                        c_obj = vars_map[idx]['cell']
                        self.set_invalid_error(c_obj, c_obj.value)
                        achados.append(analyzer_relatorio.Achado(
                            vars_map[idx].get('pergunta', ''), "invalido",
                            motivo=res.get("motivo"), especificacao=True))

        # 7. Somar Pontos IA (GANHOS)
        for k, valid in ai_valid_fixed.items():
            if valid: total_score_earned += celulas_ai_map[k]['weight']

        for idx, valid in enumerate(ai_valid_vars):
            if valid: total_score_earned += vars_map[idx]['weight']

        # [ALTERAÇÃO 2] Lógica de Normalização (0 a 100%)
        # Soma total possível = Soma dos pesos fixos + Total destinado às variáveis
        # `total_vars` e sempre > 0 aqui: a ficha sem especificacoes tecnicas
        # nao chega neste ponto (ver o `return False` la em cima). A
        # renormalizacao que existiu por algumas horas em 2026-08-26 foi
        # substituida por essa regra -- o caso nao era pontuar o que existe,
        # era recusar a ficha.
        grand_total_possible = total_possible_fixed + max_variable_points

        if grand_total_possible > 0:
            final_percentage = (total_score_earned / grand_total_possible) * 100
        else:
            final_percentage = 0.0

        final_score = int(round(final_percentage, 0))

        # 8. Decisão e Salvamento
        #
        # CAMPO OBRIGATÓRIO FALTANDO REPROVA, qualquer que seja a nota (lista
        # do usuário, 2026-08-26). Sem eles a ficha não serve para cadastro,
        # então uma nota acima do limiar não pode aprová-la -- ela vai para
        # `FT_bad` MARCADA, que é justamente o arquivo que se manda ao
        # fornecedor mostrando o que falta.
        #
        # `FT_bad` e não `FT_nao_concluidas`: aqui a análise ACONTECEU e sabe
        # dizer o que está errado. A pasta de não concluídas é para quando o
        # aplicativo não conseguiu analisar.
        aprovada = final_score >= score_threshold and not obrigatorios_faltando
        folder_status = "FT_good" if aprovada else "FT_bad"

        # Log Informativo com detalhes da normalização
        yield f"Pontos Brutos: {total_score_earned:.1f}/{grand_total_possible:.1f}"
        yield f"Nota Normalizada: {final_score}% ({folder_status})"
        if obrigatorios_faltando:
            yield (f"[REPROVADA] {len(obrigatorios_faltando)} campo(s) OBRIGATORIO(s) "
                   f"faltando ou invalido(s), entao a ficha nao e aprovada mesmo com "
                   f"nota {final_score}%:")
            for campo in obrigatorios_faltando:
                yield f"    · {campo}"

        self._registrar_no_relatorio(codigo_pmib_4, original_filename,
                                     final_score, achados)

        final_path_dir = os.path.join(root_output_dir, folder_status, subfolder_name)
        os.makedirs(final_path_dir, exist_ok=True)

        out_name = nome_com_a_nota(original_filename, final_score)
        out_path = os.path.join(final_path_dir, out_name)

        try:
            # `aprovada` e nao `final_score >= score_threshold`: a ficha
            # reprovada por campo obrigatorio precisa ir MARCADA, senao o
            # fornecedor recebe o original limpo e nao ve o que falta.
            if aprovada:
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

        # Duas correções medidas em 2026-08-26, ambas silenciosas:
        #
        # 1. `if not c_desc.value: break` parava na PRIMEIRA linha sem
        #    descrição. Uma linha de separação no meio da planilha tornava
        #    invisível todo o resto, e o analyzer dizia "PMIB não encontrado"
        #    para materiais que estavam lá. Agora a lista só acaba depois de
        #    `MAX_LINHAS_VAZIAS_SEGUIDAS` linhas em branco.
        #
        # 2. `str(c_pmib.value).strip()` não dava conta do código guardado
        #    como NÚMERO: o Excel devolve `4500063671.1050` como o float
        #    `4500063671.105` e o zero à direita evapora, então `.endswith
        #    (".1050")` nunca casava. `normalize_pmib` é a implementação
        #    única do CP 1.2 -- a mesma que o R-01 do autospec usou para o
        #    mesmo problema -- e de quebra tira o apóstrofo do Excel.
        vazias_seguidas = 0
        for row in ws.iter_rows(min_row=rstart, min_col=min_c, max_col=max_c):
            c_desc = row[d_offset]
            c_pmib = row[p_offset]

            if not c_desc.value and not c_pmib.value:
                vazias_seguidas += 1
                if vazias_seguidas >= MAX_LINHAS_VAZIAS_SEGUIDAS:
                    break  # Aqui a lista acabou de verdade
                continue
            vazias_seguidas = 0

            if c_pmib.value and c_desc.value:
                val = pmib_codes.normalize_pmib(c_pmib.value)
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
        #
        # 2026-08-26: o motivo da falha deixou de morrer no `print`. Num app
        # empacotado a janela preta não existe, e o usuário via só a nota
        # inflada, sem nenhuma pista de que a IA nem tinha sido consultada.
        # `ultimo_erro_ia` é publicado no log da tela por `processar_planilha`.
        try:
            self.ultimo_erro_ia = None
            resp = self._llm.generate(prompt, tags={"modulo": "analyzer_backend", "tarefa": "validar_ficha"})
            return resp.parsed_json
        except Exception as e:
            self.ultimo_erro_ia = f"{type(e).__name__}: {e}"
            # O `print` CONTINUA de propósito: `tests/test_llm_backend_
            # migration.py` (frente do Luan, CP 3.1) o trava como
            # caracterização -- "preserva o print de erro de hoje". Tirá-lo
            # aqui obrigaria a reescrever um teste da outra frente às vésperas
            # do CP 7.3, e o canal que a tela usa agora é `ultimo_erro_ia`.
            # A redundância está registrada em PENDENCIAS.md para o CP 8.1.
            print(f"API Error: {e}")
            return None
