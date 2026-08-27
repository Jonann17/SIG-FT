import time
import openpyxl
import pandas as pd
import os
import json
from types import SimpleNamespace

from sigft import config
from sigft.core.excel import headers, locking, pmib_codes, status_sheet
# CP 2.1 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 2): fábrica única de
# driver Chrome, substitui `webdriver.Chrome()` cru em
# `UploadAutomation.iniciar` abaixo.
# CP 5.3 (Fase 5): `upload_conditions` migrado -- o `selenium` sumiu dos
# imports. Quem decide o motor é `config.RPA_ENGINE["upload_conditions"]`.
from sigft.core.rpa.factory import criar_engine
# CP 2.2 (Fase 2): `safe_click`/`safe_send_keys`/`check_or_uncheck`/a busca-e-
# abertura inline de `processar_lista`/o stop-flag de `ConditionsProcessor` e
# `UploadAutomation` passam a delegar para `PMIBPortal`.
#
# CP 2.3 (Fase 2): os 11 `time.sleep(<literal>)` do arquivo viram
# constantes nomeadas (nenhum eliminado) -- ver
# docs/refatoracao/PLANO_REFATORACAO.md Fase 2 -> CP 2.3.
#
# CP 3.1 (Fase 3): `PAUSA_RETRY_IA_LONGA` REMOVIDA deste import -- o retry de
# IA (e o sleep entre tentativas) agora vive dentro de `LLMClient` (ver
# `sigft.core.llm.client.get_llm`); a constante continua existindo em
# `portal.py` (intocada), só este import é que fica sem uso dela.
from sigft.core.rpa.portal import (
    PMIBPortal,
    PAUSA_DIGITACAO,
    PAUSA_ENTRE_CAMPOS,
    PAUSA_FALLBACK_SALVAMENTO,
    PAUSA_SALVAMENTO,
)
# CP 3.1 (Fase 3): `google.generativeai` deixou de ser importado aqui --
# `ConditionsProcessor.processar_ia_lote` abaixo delega para `LLMClient`/
# `GeminiProvider` (ÚNICO lugar do projeto que importa `genai`).
from sigft.core.llm.client import get_llm
# CP 4.4 (Fase 4): `processar_ia_lote` emite o padrão único de log (início
# com total/contexto, linha por ficha, resumo com falhas e pulados listados).
# Forma DIRETA (`lote.sucesso/falha/pulado`), somando ao que já existia: as
# mensagens específicas por ficha ("Enviando ... para API", "Sucesso API")
# têm valor de diagnóstico e foram PRESERVADAS.
from sigft.core.callbacks import from_legacy
from sigft.core.relatorio_lote import RelatorioLote
# CP 3.5 (Fase 3): o TEXTO do `system_prompt`/`user_prompt` de
# `processar_ia_lote` abaixo mora em `sigft.core.llm.prompts`
# (`SYSTEM_CONDICOES`/`montar_condicoes_user`).
from sigft.core.llm import prompts


# =============================================================================
# CLASSES DE SERVIÇO (BACKEND PURO)
# =============================================================================
class ConditionsProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        # CP 2.2: stop-flag delega para `PMIBPortal` -- construído SEM
        # engine, porque esta classe só chama a API do Gemini (não tem
        # driver/browser nenhum). `solicitar_parada`/`deve_parar` são os
        # únicos métodos de `PMIBPortal` que nunca tocam `self.engine`, então
        # isso é seguro -- ver docstring de `PMIBPortal.__init__` e
        # docs/refatoracao/PENDENCIAS.md.
        self.portal = PMIBPortal()
        # CP 3.1: `genai.configure(...)` sai daqui -- agora vive dentro de
        # `GeminiProvider` (chamado por `get_llm`), com o MESMO guard ("só
        # configura se api_key for truthy").
        self._llm = get_llm("condicoes", api_key)

    def solicitar_parada(self):
        self.portal.solicitar_parada()

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

    def processar_ia_lote(self, lista_caminhos, df_status, callback_log=None,
                          processar_completos=False):
        """Gera o conteudo das Condicoes por IA, ficha a ficha.

        `processar_completos` (2026-08-18): quando True, reprocessa tambem as
        fichas ja marcadas como COMPLETO na coluna CONDICOES do
        `_STATUS_PMIB`. E o que o interruptor "Forcar processamento de fichas
        com status 'COMPLETO'" da tela sempre prometeu.

        O interruptor existia na UI desde o inicio (`ModuloUploadConditions.
        var_processar_completos`), mas NUNCA foi lido: nem `_start_ia_process`
        chamava `.get()`, nem esta funcao tinha o parametro. O proprio
        frontend registrava a divida por escrito -- "para manter simples,
        vamos rodar; se o usuario quiser forcar, ele deveria alterar o Excel,
        ou precisaremos adicionar essa logica no backend no futuro". Ou seja:
        um controle que nao controlava nada, e que dava ao usuario a
        impressao contraria da verdade.

        O default e False para preservar o comportamento de quem chama sem o
        argumento (economia de API continua sendo o padrao).
        """
        fichas_processadas = []
        # CP 4.4: `from_legacy` adapta o `callback_log` antigo sem mudar a
        # assinatura pública desta função (o frontend segue chamando igual).
        lote = RelatorioLote(
            from_legacy(callback_log=callback_log),
            titulo="Condições — gerando conteúdo por IA",
            total=len(lista_caminhos),
            contexto={
                "fichas": len(lista_caminhos),
                "forçar COMPLETO": "sim" if processar_completos else "não",
            },
        )
        lote.iniciar()
        # CP 1.2: prefixo de contrato deriva de config.PREFIXO_CONTRATO (era
        # hardcoded "4500063671" aqui); ver
        # core.excel.pmib_codes.extract_contract_pmib_code, usada abaixo.

        # CP 3.5 (docs/refatoracao/PLANO_REFATORACAO.md, Fase 3): o TEXTO
        # deste system prompt (estático -- antes embutido aqui) agora mora em
        # `sigft.core.llm.prompts.SYSTEM_CONDICOES`.
        system_prompt = prompts.SYSTEM_CONDICOES

        # CP 3.1: `safety_settings` (BLOCK_NONE) sai daqui -- agora vive
        # dentro de `GeminiProvider` (aplicado a TODA chamada, não só a
        # `condicoes`/`tech_specs` -- ver docs/refatoracao/PENDENCIAS.md).

        for caminho in lista_caminhos:
            if self.portal.deve_parar():
                if callback_log: callback_log("Processamento de IA interrompido pelo usuário.")
                break  # Sai do loop principal

            nome_arquivo = os.path.basename(caminho)
            pmib_codigo = pmib_codes.extract_contract_pmib_code(caminho)
            if not pmib_codigo:
                if callback_log: callback_log(f"Ignorado (Sem PMIB): {nome_arquivo}")
                lote.pulado(nome_arquivo, "nome do arquivo não contém código PMIB do contrato")
                continue

            try:
                status_atual = df_status.loc[pmib_codigo, 'CONDIÇÕES']

                # Se houver PMIBs duplicados na planilha, o Pandas retorna uma Series.
                # Seguindo sua regra, pegamos apenas a primeira célula.
                if isinstance(status_atual, pd.Series):
                    status_atual = status_atual.iloc[0]

                if str(status_atual).strip().upper() == "COMPLETO":
                    if processar_completos:
                        # Reprocessa. A linha de log e deliberada: sem ela, o
                        # unico sinal de que o interruptor funcionou seria a
                        # AUSENCIA da mensagem "ja COMPLETO" -- e ausencia de
                        # mensagem nao e evidencia que o usuario consiga ver.
                        if callback_log:
                            callback_log(f"PMIB {pmib_codigo} está COMPLETO, mas o "
                                         f"'Forçar processamento' está ligado -- reprocessando.")
                    else:
                        if callback_log: callback_log(f"PMIB {pmib_codigo} já COMPLETO.")
                        lote.pulado(pmib_codigo, "já marcado como COMPLETO no STATUS_PMIB")
                        continue
            except KeyError:
                pass

            dados_brutos = self.extrair_dados_brutos_excel(caminho)
            if not dados_brutos:
                lote.pulado(pmib_codigo, "não foi possível extrair dados da planilha")
                continue

            # O portal recusa campo vazio, então a IA preenche esses com "N/A"
            # (ver SYSTEM_CONDICOES, REGRA 0). Dizer QUAIS vieram vazios é o
            # que separa "o fornecedor respondeu N/A" de "o fornecedor não
            # respondeu" -- no portal os dois ficam idênticos.
            vazios = campos_em_branco_na_origem(dados_brutos)
            if vazios and callback_log:
                callback_log(f"   [i] {pmib_codigo}: {len(vazios)} campo(s) sem resposta do "
                             f"fornecedor, irão como 'N/A': {', '.join(vazios)}")

            try:
                descricao = df_status.loc[pmib_codigo, 'DESCRIÇÃO']

                # Mesma proteção contra duplicatas para a descrição não ir "suja" para a IA
                if isinstance(descricao, pd.Series):
                    descricao = descricao.iloc[0]
            except Exception:
                descricao = dados_brutos.get('descricao_breve', 'N/A')

            dados_api_input = {
                "pmib_codigo": pmib_codigo,
                # As DUAS descrições vão juntas, e isso é deliberado: desde
                # 2026-08-19 a IA precisa saber O QUE é o material para deduzir
                # a unidade das medidas (ver regra 3 do SYSTEM_CONDICOES, e o
                # pedido do usuário: *"a maioria das fichas não virá unidade,
                # mas sabendo o tipo de material..."*). Quanto mais sinal sobre
                # o material, melhor a dedução -- e as duas fontes falham em
                # situações diferentes: a do `_STATUS_PMIB` é a melhor quando
                # existe, mas o código pode não estar na planilha; o H6 é da
                # própria ficha e está sempre lá, ainda que mais pobre.
                'Descrição do material': descricao,
                'Descrição breve da ficha': dados_brutos.get('descricao_breve', ''),
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

            # CP 3.5: o TEXTO deste prompt de usuário agora mora em
            # `sigft.core.llm.prompts.montar_condicoes_user` -- a
            # serialização do JSON continua aqui (só o texto muda de
            # arquivo, resultado em runtime é byte-idêntico).
            dados_api_input_json = json.dumps(dados_api_input, indent=2, ensure_ascii=False)
            user_prompt = prompts.montar_condicoes_user(dados_api_input_json)

            # CP 3.1: retry (3 tentativas, 30s entre elas) + limpeza/parse do
            # JSON da resposta agora vivem dentro de `LLMClient.generate()`
            # (`self._llm`, resolvido em `__init__` via
            # `get_llm("condicoes", ...)`) -- este bloco vira uma única
            # chamada com um try/except fino. Preserva os logs POR FICHA
            # ("Enviando ... para API", "Sucesso API", "Falha definitiva no
            # PMIB ...") -- só os logs GRANULARES por TENTATIVA ("Tentativa
            # N/3...", "Aguardando 30 segundos...", "Erro na tentativa
            # N...") deixam de existir, já que o retry passa a acontecer
            # dentro do `LLMClient`, sem hook de log por tentativa -- ver
            # docs/refatoracao/PENDENCIAS.md.
            try:
                if callback_log: callback_log(f"Enviando {pmib_codigo} para API...")
                resp = self._llm.generate(
                    user_prompt,
                    system=system_prompt,
                    tags={"modulo": "upload_conditions_backend", "tarefa": "condicoes"},
                )
                res_json = resp.parsed_json
                res_json["pmib_codigo"] = pmib_codigo
                fichas_processadas.append(res_json)
                if callback_log: callback_log(f"Sucesso API: {pmib_codigo}")
                lote.sucesso(pmib_codigo)
            except Exception as e:
                if callback_log: callback_log(f"Falha definitiva no PMIB {pmib_codigo}: {e}")
                lote.falha(pmib_codigo, f"{type(e).__name__}: {e}")

        lote.finalizar()
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

            # 5. Salvar -- CP 1.3: delega para locking.save_with_retry (única
            # implementação de retry de PermissionError). `pandas.DataFrame`
            # não tem `.save(path)`; adapta com um objeto duck-typed mínimo.
            # `max_attempts=1` preserva o comportamento ORIGINAL desta
            # variante (log + sai): nenhuma retentativa, aborta na 1ª
            # PermissionError (relevantada e capturada pelo `except`
            # abaixo, exatamente como antes).
            _adaptador_save = SimpleNamespace(save=lambda caminho: df_final.to_excel(caminho, index=False))
            locking.save_with_retry(_adaptador_save, caminho_existente, max_attempts=1)

            return True, f"Dados anexados com sucesso!\nTotal de registros agora: {len(df_final)}"

        except PermissionError:
            return False, "Erro de Permissão: O arquivo Excel está aberto. Feche-o e tente novamente."
        except Exception as e:
            return False, f"Erro ao anexar dados: {e}"


# =============================================================================
# CLASSE DE AUTOMAÇÃO (SELENIUM)
# =============================================================================
# CP 5.3: os 2 checkboxes que servem de âncora para a navegação por TAB dos
# campos de temperatura/umidade. Aparecem 2x cada (marcar + focar), então
# viram constantes em vez de literal repetido.
XPATH_CHECK_CLIMATIZACAO = '//*[@id="b10-b17-b1-Checkbox4"]'
XPATH_CHECK_UMIDADE = '//*[@id="b10-b17-b1-Checkbox5"]'


# ---------------------------------------------------------------------------
# Pendências de uma ficha (2026-08-18)
# ---------------------------------------------------------------------------
# Antes, cada bloco de campos terminava em
#
#     except Exception as e:
#         if callback_log: callback_log(f"Aviso: Falha nas Dimensões. {e}")
#
# e o laço seguia. No fim, `processar_lista` marcava a ficha como COMPLETO no
# `_STATUS_PMIB` INCONDICIONALMENTE -- ou seja, uma ficha em que os 12 blocos
# falharam saía marcada como pronta. A informação existia, na tela, e era
# jogada fora na linha seguinte.
#
# A mensagem de log é a MESMA de antes, byte a byte: o objetivo aqui não é
# melhorar o texto, é parar de perder o fato.
# As quatro seções de Condições que ESTE módulo preenche, na ordem da tela.
#
# A quinta ("Valorização" / financeira) fica FORA de propósito: o módulo não a
# preenche, então exigir confirmação dela deixaria toda ficha INCOMPLETO para
# sempre. É o "salvo a parte da valorização" do pedido do usuário -- e é
# também a mesma exclusão que `duplicadas_spec.e_aba_financeira` faz do outro
# lado do sistema, por outro motivo (não copiar dado financeiro entre fichas).
# Campos que o fornecedor pode deixar em branco na ficha e que o PORTAL exige
# preenchidos. O prompt manda a IA devolver "No aplicable" (ES) / "Não
# aplicável" (PT) neles (ver `SYSTEM_CONDICOES`, REGRA 0) -- senão a gravação
# falha e a ficha inteira não salva.
#
# Esta lista NÃO muda o que é enviado: serve para o LOG dizer quais vieram
# vazios da planilha. Sem isso, "N/A" no portal fica indistinguível de "o
# fornecedor respondeu N/A", e quem revisa não sabe o que conferir.
CAMPOS_QUE_O_PORTAL_EXIGE = (
    "embalagem_transp", "posicao_icagem", "cuidad_preserv", "limpeza_secagem",
    "ferramentas", "legislacao", "descarte",
)


def _sem_acento(texto):
    from unicodedata import normalize
    return normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()


def campos_em_branco_na_origem(dados_brutos):
    """Quais dos campos exigidos vieram vazios da planilha do fornecedor."""
    vazios = []
    for campo in CAMPOS_QUE_O_PORTAL_EXIGE:
        valor = str((dados_brutos or {}).get(campo) or "").strip()
        # As formas por extenso entram junto das abreviações: o fornecedor que
        # escreve "não aplicável" está dizendo a MESMA coisa que o que escreve
        # "N/A", e quem revisa precisa saber que nenhum dos dois é informação.
        if not valor or _sem_acento(valor).lower() in (
                "n/a", "na", "nan", "none", "-",
                "nao aplicavel", "no aplicable", "nao se aplica", "no se aplica"):
            vazios.append(campo)
    return vazios


# Quanto se espera a aba de Condições assentar depois do clique.
#
# ⚠️ Esta constante existe por causa de um defeito MEDIDO em 2026-08-19, no
# primeiro lote real depois da migração: em cada seção, o PRIMEIRO campo --
# sempre o de espanhol, sempre a linha logo após o clique da aba -- chegava
# vazio ao portal, e a gravação morria com "Por favor, verifique os campos".
#
# O que provou que o defeito é do ROBÔ e não da IA: o Excel gerado no mesmo
# lote (31 fichas) tem ZERO células de texto vazias. `legislacao_es`,
# `cuidad_preserv_es` e `embalagem_transp_es` estavam todos preenchidos. O
# valor existia e não chegava na tela.
#
# A aba do OutSystems RE-RENDERIZA o conteúdo ao ser ativada. O robô escrevia
# no campo antes de a renderização assentar, e o re-render limpava o que ele
# tinha acabado de escrever -- por isso só o primeiro campo se perdia: quando
# chegava no segundo, a tela já tinha assentado.
PAUSA_ABA_ASSENTAR = 1.0

# Quanto se espera o campo numérico assentar antes de RELER.
#
# O portal reformata o que recebe (máscara de decimal), e a releitura imediata
# pega o campo no meio da reformatação. Medido no lote de 2026-08-19: o alvo
# "10" foi lido como "1" -- o primeiro caractere --, o que só acontece se a
# leitura chega antes de a máscara terminar.
PAUSA_CAMPO_ASSENTAR = 0.35


def _para_numero(texto):
    """`",55"` / `"0,55"` / `"0.55"` / `"1.234,56"` -> float. Não numérico -> `None`.

    ⚠️ A VÍRGULA DECIDE quem é separador decimal, e a primeira versão disto
    errava: ela removia todo ponto antes de converter, então `"0.5"` virava
    `"05"` = **5,0** -- dez vezes o valor. Passaria despercebido justamente no
    caso em que o portal devolvesse o número com ponto, e a conferência
    aprovaria um valor errado ou reprovaria um certo.

    A regra que vale nos dois formatos do domínio:

        tem vírgula  -> vírgula é o decimal, ponto é milhar ("1.234,56")
        sem vírgula  -> ponto é o decimal ("0.5")
    """
    bruto = str(texto if texto is not None else "").strip()
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    if not bruto or bruto in (".", "-", "-."):
        return None
    try:
        return float(bruto)
    except ValueError:
        return None


def mesmo_valor(escrito, na_tela):
    """O que ficou na tela é o MESMO valor que pedimos?

    ⚠️ COMPARAÇÃO NUMÉRICA, e não de texto. É o conserto de um falso positivo
    que gerou 28 fichas "INCOMPLETO" num lote em que o portal tinha aceitado
    tudo (2026-08-19):

        pedimos ",55"   o portal guardou "0,55"   -> texto difere, número não

    ⚠️ ONDE a normalização acontece, corrigido em 2026-08-19 com o HTML do
    campo na mão:

        <input type="text" maxlength="30" data-os-type="text"
               data-os-pattern="" inputmode="decimal">

    `data-os-pattern` VAZIO e `data-os-type="text"`: o campo **não tem
    máscara** e não reformata nada na digitação. `inputmode="decimal"` é só
    dica de teclado de celular. Então o zero à esquerda NÃO é reposto quando
    se escreve -- ele aparece depois de SALVAR, quando o servidor grava o
    número e re-renderiza a tela.

    Isso importa para quem for mexer aqui: numa ficha já salva antes, o campo
    chega com "0,55" e o que a gente escreve é ",55". Comparar texto fazia
    toda dimensão e todo peso menor que 1 virar pendência -- e um alarme que
    dispara sempre é igual a alarme nenhum: some no meio do log, e o real some
    junto.

    Um valor REALMENTE perdido continua sendo pego, porque aí o número muda
    mesmo: ",003" virando "0,0" é perda de precisão de verdade, e "10" virando
    "1" também.

    Sem número dos dois lados (texto livre), cai para a comparação de texto,
    que é o comportamento correto ali.
    """
    a, b = _para_numero(escrito), _para_numero(na_tela)
    if a is None or b is None:
        return str(escrito or "").strip() == str(na_tela or "").strip()
    return a == b


SECOES_DE_CONDICOES = ("Armazenamento", "Transporte", "Manutenção", "Descarte")


def _registrar_pendencia(pendencias, onde, erro, callback_log=None):
    pendencias.append(f"{onde}: {type(erro).__name__}: {erro}")
    if callback_log:
        callback_log(f"Aviso: Falha {onde}. {erro}")


class UploadAutomation:
    def __init__(self):
        self.engine = None
        # CP 2.2: `self.portal` (SEM engine ainda) já nasce aqui -- não só em
        # `iniciar()` -- para que `solicitar_parada()` continue seguro de
        # chamar a QUALQUER momento, inclusive ANTES de `iniciar()` rodar
        # (cenário real: `frontend.py` atribui a instância a
        # `self.automacao_ativa` e só DEPOIS a thread de trabalho chega a
        # `iniciar()`; o botão "Parar" pode disparar nesse meio-tempo).
        # `iniciar()` abaixo só ANEXA o engine à MESMA instância de
        # `PMIBPortal` (preserva um stop-flag já setado, se houver) -- ver
        # docs/refatoracao/PENDENCIAS.md.
        self.portal = PMIBPortal()

    def solicitar_parada(self):
        self.portal.solicitar_parada()

    def iniciar(self):
        """CP 2.1: a criação em si (Chrome + maximize + WebDriverWait(20s))
        agora vem de `create_chrome_driver` (única fábrica, ver
        core/rpa/selenium_engine.py) — timeout preservado EXATAMENTE como
        antes (20s).

        CP 2.2: `self.portal` (já existente desde `__init__`, ver acima)
        ganha o `engine` de verdade (`SeleniumEngine` sobre o MESMO
        `driver`/`wait`) -- `safe_click`/`safe_send_keys`/`check_or_uncheck`/
        `processar_lista` abaixo passam a delegar para ele.
        """
        self.engine = criar_engine("upload_conditions", wait_timeout=20)
        self.portal.engine = self.engine
        return self.engine

    # --- NOVO MÉTODO PARA CORRIGIR O ERRO DA URL DATA:, ---
    def abrir_portal(self, url):
        """Carrega a URL fornecida no navegador já aberto."""
        if self.engine:
            self.engine.goto(url)
    # ------------------------------------------------------

    def fechar(self):
        if self.engine:
            self.engine.fechar()

    def safe_click(self, locator):
        """CP 2.2: DELEGADOR FINO -- a mecânica real agora vive em
        `PMIBPortal.safe_click`/`SeleniumEngine.click` (um único lugar).
        `locator` continua aceito como tupla `(By.XPATH, xpath)` -- é assim
        que os MUITOS call sites internos desta classe já chamam hoje; a
        string XPath é extraída aqui antes de repassar."""
        seletor = locator[1] if isinstance(locator, tuple) else locator
        self.portal.safe_click(seletor)

    def safe_send_keys(self, locator, text):
        """CP 2.2: DELEGADOR FINO para `PMIBPortal.safe_fill`/
        `SeleniumEngine.fill` -- mesma extração de XPath de `safe_click`
        acima."""
        seletor = locator[1] if isinstance(locator, tuple) else locator
        self.portal.safe_fill(seletor, text)

    def check_or_uncheck(self, locator, should_check):
        """CP 2.2: DELEGADOR FINO para `PMIBPortal.check_or_uncheck` --
        mesma extração de XPath de `safe_click`/`safe_send_keys` acima."""
        seletor = locator[1] if isinstance(locator, tuple) else locator
        self.portal.check_or_uncheck(seletor, should_check)

    def abrir_aba(self, seletor_aba, seletor_primeiro_campo, nome, callback_log=None):
        """Clica na aba e ESPERA ela assentar antes de devolver.

        A espera é pelo primeiro campo ficar visível, e não um `sleep` cego: o
        campo visível é a evidência de que a re-renderização terminou. O
        `sleep` fica como piso mínimo depois disso, porque "visível" e
        "estável" não são a mesma coisa num widget que anima.

        Ver `PAUSA_ABA_ASSENTAR` para o defeito que motivou isto.
        """
        self.safe_click(seletor_aba)
        try:
            self.engine.wait_visible(seletor_primeiro_campo)
        except Exception:  # noqa: BLE001
            if callback_log:
                callback_log(f"      [!] A aba '{nome}' não mostrou o primeiro campo a tempo. "
                             f"Vou tentar preencher assim mesmo.")
        time.sleep(PAUSA_ABA_ASSENTAR)

    def _escrever(self, seletor, texto, nome_campo, callback_log=None):
        """Escreve DIZENDO por que falhou, em vez de engolir.

        `safe_send_keys` delega para `engine.fill`, que engole a exceção por
        contrato. Isso é o certo em quase todo lugar -- e é péssimo aqui: sem
        máscara no campo (ver `mesmo_valor`), uma releitura que discorda do que
        se escreveu só pode significar que **a escrita não aconteceu**. Saber
        POR QUE ela não aconteceu é a diferença entre "conserto isto amanhã" e
        "abro o portal e vou adivinhando".

        Ele **não engole** a falha: loga o motivo e repassa, para o bloco da
        seção continuar registrando a pendência como sempre registrou.
        """
        try:
            self.engine.fill_estrito(seletor, str(texto))
        except Exception as erro:  # noqa: BLE001 -- ver docstring
            if callback_log:
                callback_log(f"      [!] Não consegui escrever em '{nome_campo}': "
                             f"{type(erro).__name__}: {erro}")
            # ⚠️ REPASSA. A primeira versão disto só logava, e com isso tirou a
            # falha do caminho que a registrava: o bloco da seção deixava de
            # cair no `except`, nenhuma pendência era criada e a ficha saía
            # COMPLETO com o campo vazio -- ou seja, eu tinha reaberto o
            # próprio defeito que o COMPLETO-com-prova existe para fechar.
            # Um teste pegou. O que este método acrescenta é o MOTIVO no log,
            # não a supressão da falha.
            raise

    def preencher_conferindo(self, seletor, texto, nome_campo,
                             callback_log=None, pendencias=None):
        """Escreve, RELÊ e reescreve uma vez se o portal engoliu o valor.

        É o mesmo remédio que `tech_specs._preencher_input_com_auditoria` já
        usava ("o site zerou o valor"), agora em Condições -- onde ele faltava
        e custou um lote inteiro.

        Devolve `True` se o campo terminou com o texto pedido. Texto vazio não
        é conferido: o portal exige campo preenchido, mas quem decide o que vai
        nele é a IA (ver `SYSTEM_CONDICOES`), e um campo que o JSON mandou
        vazio é problema de outra camada -- reclamar dele aqui só criaria
        ruído em cima de um defeito que já tem dono.
        """
        alvo = str(texto or "")
        self._escrever(seletor, alvo, nome_campo, callback_log)
        if not alvo.strip():
            return True

        for tentativa in (1, 2):
            # Dá um tempo para a máscara do portal terminar antes de ler. Sem
            # isto a leitura pega o campo no meio da reformatação -- foi assim
            # que "10" apareceu como "1" no lote de 2026-08-19.
            time.sleep(PAUSA_CAMPO_ASSENTAR)
            try:
                atual = str(self.engine.get_value(seletor) or "")
            except Exception:  # noqa: BLE001
                return True  # não dá para conferir; não inventa pendência
            if mesmo_valor(alvo, atual):
                return True
            if tentativa == 1:
                if callback_log:
                    callback_log(f"      [!] '{nome_campo}': pedi {alvo.strip()[:20]!r} e "
                                 f"ficou {atual.strip()[:20]!r}. Reescrevendo.")
                self._escrever(seletor, alvo, nome_campo, callback_log)

        if callback_log:
            callback_log(f"      [!] '{nome_campo}' NÃO aceitou {alvo.strip()[:20]!r} em duas "
                         f"tentativas (ficou {atual.strip()[:20]!r}) -- preencher à mão.")
        if pendencias is not None:
            pendencias.append(f"campo '{nome_campo}' não aceitou o valor")
        return False

    def processar_lista(self, lista_fichas, caminho_status, callback_ask=None, callback_log=None, callback_pause=None):
        """Preenche as Condições de cada ficha no portal.

        Devolve `(completas, incompletas)` -- as listas de PMIB. O retorno é
        novo (2026-08-18) e aditivo: a tela ignorava o `None` de antes.

        Uma ficha só é marcada COMPLETO no `_STATUS_PMIB` quando NENHUM bloco
        de campos falhou E o portal confirmou o salvamento das 4 seções. Ver
        `SECOES_DE_CONDICOES` e `_registrar_pendencia`.
        """
        # [CP 8.1] A variavel `url` saiu: ela sobrou de quando esta funcao
        # fazia `driver.get(url)` aqui. O `abrir_portal` passou a ser chamado
        # pelo App ANTES do login, e desde entao ninguem lia a variavel --
        # so o comentario abaixo, que fica porque explica o PORQUE.
        # O endereco do portal, quando preciso, vem de `config.PORTAL_URL`.
        # O App chama 'abrir_portal' ANTES de pedir o login.
        lote_completas = []
        lote_incompletas = []

        for ficha in lista_fichas:
            if self.portal.deve_parar():
                if callback_log: callback_log("Automação Web interrompida pelo usuário.")
                break  # Quebra o loop principal e vai para o finally de fechamento

            pmib = ficha['pmib_codigo']
            if callback_log: callback_log(f"Processando {pmib}...")

            # Placar desta ficha. `pendencias` junta os blocos de campos que
            # falharam; `salvas` diz quais das 4 seções o PORTAL confirmou ter
            # gravado. Juntos são o que decide o COMPLETO lá embaixo -- ver
            # `_secoes_todas_confirmadas`.
            pendencias = []
            salvas = {}

            try:
                # 1. Busca e abre a ficha em modo de edição.
                #
                # CP 2.2: delega para `PMIBPortal.pesquisar_e_abrir` com os
                # seletores EXATOS que este módulo já usava (placeholder
                # completo do campo de busca; ícone `fa-pencil-square-o`,
                # DIFERENTE de `fa-pencil` usado por `apagar_lmr`/
                # `upload_tech_specs`) -- ver docstring de `PMIBPortal.
                # pesquisar_e_abrir`. O retorno `bool` é intencionalmente
                # DESCARTADO aqui: o ORIGINAL não tinha NENHUM sinal de
                # sucesso/falha nesta etapa (`safe_click`/`safe_send_keys`
                # sempre engoliam exceção silenciosamente; `driver.get(url)`
                # não falha por si só) -- preservado tal qual (mesmo silêncio
                # de antes, não uma correção deste checkpoint); ver
                # docs/refatoracao/PENDENCIAS.md.
                self.portal.pesquisar_e_abrir(
                    pmib,
                    busca_xpath="//input[@placeholder='Código, Nome ES/PT pela Ficha Técnica, Código do projeto e/ou contrato']",
                    lapis_xpath_template="//span[text()='{pmib}']/ancestor::tr//a[.//i[contains(@class, 'fa-pencil-square-o')]]",
                )

                # --- ABA 1: CONDIÇÕES (ARMAZENAMENTO) ---
                try:
                    self.safe_click('//*[@id="b10-Conditions_Header"]/button')
                except Exception as e:
                    if callback_log: callback_log(f"ERRO: Não abriu aba Condições. {e}")
                    continue  # Pula ficha se falhar a aba principal

                try:
                    self.preencher_conferindo('//*[@id="b10-b17-b1-Input_PackingLength"]', ficha["dimensoes"]["comprimento"],
                                              "Input_PackingLength", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b1-Input_PackagingWidth"]', ficha["dimensoes"]["largura"],
                                              "Input_PackagingWidth", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b1-Input_PackagingHeight"]', ficha["dimensoes"]["altura"],
                                              "Input_PackagingHeight", callback_log, pendencias)
                except Exception as e:
                    _registrar_pendencia(pendencias, "nas Dimensões", e, callback_log)

                try:
                    controle_temp_data = ficha["controle_temperatura"]
                    if controle_temp_data["necessidade"] == "SIM":
                        self.safe_click('//*[@id="b10-b17-b1-RadioButton5-input"]')
                        if controle_temp_data["climatizacao"]["ativo"]:
                            # CP 5.3: `wait.until(clickable).send_keys(TAB)` +
                            # `driver.switch_to.active_element.send_keys(...)`
                            # viraram `focar` + `press` + `digitar_no_foco`.
                            # A navegação por TAB é preservada porque os campos
                            # de temperatura não têm seletor próprio validado --
                            # trocar isso por seletor direto é o tipo de
                            # mudança que o plano reserva para depois do módulo
                            # estar estável no motor novo.
                            self.check_or_uncheck(XPATH_CHECK_CLIMATIZACAO, True)
                            self.engine.focar(XPATH_CHECK_CLIMATIZACAO)
                            self.engine.press("TAB")
                            time.sleep(PAUSA_DIGITACAO)
                            self.engine.digitar_no_foco(controle_temp_data["climatizacao"]["temp_max"])
                            time.sleep(PAUSA_ENTRE_CAMPOS)
                            self.engine.press("TAB")
                            time.sleep(PAUSA_DIGITACAO)
                            self.engine.digitar_no_foco(controle_temp_data["climatizacao"]["temp_min"])
                            time.sleep(PAUSA_ENTRE_CAMPOS)
                        if controle_temp_data["umidade"]["ativo"]:
                            self.check_or_uncheck(XPATH_CHECK_UMIDADE, True)
                            self.engine.focar(XPATH_CHECK_UMIDADE)
                            self.engine.press("TAB")
                            time.sleep(PAUSA_DIGITACAO)
                            self.engine.digitar_no_foco(controle_temp_data["umidade"]["hr_max"])
                            time.sleep(PAUSA_ENTRE_CAMPOS)
                            self.engine.press("TAB")
                            time.sleep(PAUSA_DIGITACAO)
                            self.engine.digitar_no_foco(controle_temp_data["umidade"]["hr_min"])
                            time.sleep(PAUSA_ENTRE_CAMPOS)
                    else:
                        self.safe_click('//*[@id="b10-b17-b1-RadioButton4-input"]')
                except Exception as e:
                    _registrar_pendencia(pendencias, "em Temperatura", e, callback_log)

                try:
                    posicoes = {
                        "Vertical": '//*[@id="b10-b17-b1-RadioButton-input"]',
                        "Horizontal": '//*[@id="b10-b17-b1-RadioButton7-input"]',
                        "Indiferente": '//*[@id="b10-b17-b1-RadioButton8-input"]'
                    }
                    if ficha.get("posicao_armazenamento") in posicoes:
                        self.safe_click(posicoes[ficha["posicao_armazenamento"]])
                except Exception as e:
                    _registrar_pendencia(pendencias, "na Posição", e, callback_log)

                try:
                    nocivo_data = ficha["nocivo"]
                    if nocivo_data["status"] == "Nocivo":
                        self.safe_click('//*[@id="b10-b17-b1-RadioButton2-input"]')
                        self.preencher_conferindo('//*[@id="b10-b17-b1-TextArea_StorageCareES"]', nocivo_data["cuidado_es"],
                                                  "TextArea_StorageCareES", callback_log, pendencias)
                        self.preencher_conferindo('//*[@id="b10-b17-b1-TextArea_StorageCarePT"]', nocivo_data["cuidado_pt"],
                                                  "TextArea_StorageCarePT", callback_log, pendencias)
                    else:
                        self.safe_click('//*[@id="b10-b17-b1-RadioButton1-input"]')
                except Exception as e:
                    _registrar_pendencia(pendencias, "em Nocivo", e, callback_log)

                try:
                    self.preencher_conferindo('//*[@id="b10-b17-b1-Input_LiquidWeight"]', ficha["peso"]["liquido"],
                                              "Input_LiquidWeight", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b1-Input_GrossWeight"]', ficha["peso"]["bruto"],
                                              "Input_GrossWeight", callback_log, pendencias)
                except Exception as e:
                    _registrar_pendencia(pendencias, "nos Pesos", e, callback_log)

                if ficha["controle_temperatura"]["necessidade"] == "NÃO":
                    try:
                        self.check_or_uncheck('//*[@id="b10-b17-b1-Checkbox3"]', ficha.get("sujeito_intemperie") == "SIM")
                    except Exception as e:
                        _registrar_pendencia(pendencias, "em Intempérie", e, callback_log)

                try:
                    mapa_protecao = {
                        "SN": '//*[@id="b10-b17-b1-Checkbox6"]',
                        "UV": '//*[@id="b10-b17-b1-Checkbox7"]',
                        "EL": '//*[@id="b10-b17-b1-Checkbox8"]'
                    }
                    for loc in mapa_protecao.values():
                        self.check_or_uncheck(loc, False)
                    for prot in ficha.get("protecao", []):
                        if prot in mapa_protecao:
                            self.check_or_uncheck(mapa_protecao[prot], True)
                except Exception as e:
                    _registrar_pendencia(pendencias, "na Proteção", e, callback_log)

                try:
                    self.preencher_conferindo('//*[@id="b10-b17-b1-Input_Stacking"]', ficha.get("empilhamento", ""),
                                              "Input_Stacking", callback_log, pendencias)
                except Exception as e:
                    _registrar_pendencia(pendencias, "no Empilhamento", e, callback_log)

                try:
                    cuidados_data = ficha["outros_cuidados"]
                    if cuidados_data["status"] == "SIM":
                        self.safe_click('//*[@id="b10-b17-b1-RadioButton6-input"]')
                        self.preencher_conferindo('//*[@id="b10-b17-b1-TextArea_OtherCareES"]', cuidados_data["cuidado_es"],
                                                  "TextArea_OtherCareES", callback_log, pendencias)
                        self.preencher_conferindo('//*[@id="b10-b17-b1-TextArea_OtherCarePT"]', cuidados_data["cuidado_pt"],
                                                  "TextArea_OtherCarePT", callback_log, pendencias)
                    else:
                        self.safe_click('//*[@id="b10-b17-b1-RadioButton3-input"]')
                except Exception as e:
                    _registrar_pendencia(pendencias, "em Outros Cuidados", e, callback_log)

                salvas["Armazenamento"] = self.safe_save_with_pause('//*[@id="b10-b17-b1-b35-Button"]/button', "Armazenamento", callback_log, callback_pause)

                # --- ABA 2: TRANSPORTE ---
                try:
                    # A aba re-renderiza ao abrir e limpava o 1º campo escrito.
                    self.abrir_aba('//*[@id="b10-b17-Title"]/div[3]',
                                   '//*[@id="b10-b17-b3-TextArea_TransportPackagingES"]', "Transporte", callback_log)
                    self.preencher_conferindo('//*[@id="b10-b17-b3-TextArea_TransportPackagingES"]', ficha.get("embalagem_transp_es", ""),
                                              "TextArea_TransportPackagingES", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b3-TextArea_TransportPackagingPT"]', ficha.get("embalagem_transp_pt", ""),
                                              "TextArea_TransportPackagingPT", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b3-TextArea_PositionCareES"]', ficha.get("posicao_icagem_es", ""),
                                              "TextArea_PositionCareES", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b3-TextArea_PositionCarePT"]', ficha.get("posicao_icagem_pt", ""),
                                              "TextArea_PositionCarePT", callback_log, pendencias)
                except Exception as e:
                    _registrar_pendencia(pendencias, "na aba Transporte", e, callback_log)

                salvas["Transporte"] = self.safe_save_with_pause('//*[@id="b10-b17-$b3"]/div[3]/button', "Transporte", callback_log, callback_pause)

                # --- ABA 3: MANUTENÇÃO ---
                try:
                    # A aba re-renderiza ao abrir e limpava o 1º campo escrito.
                    self.abrir_aba('//*[@id="b10-b17-Title"]/div[4]',
                                   '//*[@id="b10-b17-b4-TextArea_PreservationCareES"]', "Manutenção", callback_log)
                    self.preencher_conferindo('//*[@id="b10-b17-b4-TextArea_PreservationCareES"]', ficha.get("cuidad_preserv_es", ""),
                                              "TextArea_PreservationCareES", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b4-TextArea_PreservationCarePT"]', ficha.get("cuidad_preserv_pt", ""),
                                              "TextArea_PreservationCarePT", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b4-TextArea_CleaningMethodES"]', ficha.get("limpeza_secagem_es", ""),
                                              "TextArea_CleaningMethodES", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b4-TextArea_CleaningMethodPT"]', ficha.get("limpeza_secagem_pt", ""),
                                              "TextArea_CleaningMethodPT", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b4-TextArea_ToolPreservationES"]', ficha.get("ferramentas_es", ""),
                                              "TextArea_ToolPreservationES", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b4-TextArea_ToolPreservationPT"]', ficha.get("ferramentas_pt", ""),
                                              "TextArea_ToolPreservationPT", callback_log, pendencias)
                except Exception as e:
                    _registrar_pendencia(pendencias, "na aba Manutenção", e, callback_log)

                salvas["Manutenção"] = self.safe_save_with_pause('//*[@id="b10-b17-$b4"]/div[4]/button', "Manutenção", callback_log, callback_pause)

                # --- ABA 4: DESCARTE ---
                try:
                    # A aba re-renderiza ao abrir e limpava o 1º campo escrito.
                    self.abrir_aba('//*[@id="b10-b17-Title"]/div[5]',
                                   '//*[@id="b10-b17-b5-TextArea_TypeLegislationES"]', "Descarte", callback_log)
                    self.preencher_conferindo('//*[@id="b10-b17-b5-TextArea_TypeLegislationES"]', ficha.get("legislacao_es", ""),
                                              "TextArea_TypeLegislationES", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b5-TextArea_TypeLegislationPT"]', ficha.get("legislacao_pt", ""),
                                              "TextArea_TypeLegislationPT", callback_log, pendencias)

                    if ficha.get("perigoso_10004") == "SIM":
                        self.safe_click('//*[@id="b10-b17-b5-RadioButton1-input"]')
                    else:
                        self.safe_click('//*[@id="b10-b17-b5-RadioButton2-input"]')

                    self.preencher_conferindo('//*[@id="b10-b17-b5-TextArea_DiscardTypeES"]', ficha.get("descarte_es", ""),

                                              "TextArea_DiscardTypeES", callback_log, pendencias)
                    self.preencher_conferindo('//*[@id="b10-b17-b5-TextArea_DiscardTypePT"]', ficha.get("descarte_pt", ""),
                                              "TextArea_DiscardTypePT", callback_log, pendencias)

                    logistica_rev = ficha.get("logistica_reversa", {})
                    if logistica_rev.get("status") == "SIM":
                        self.safe_click('//*[@id="b10-b17-b5-Applies-input"]')
                        self.preencher_conferindo('//*[@id="b10-b17-b5-TextArea_ReserveLogisticES"]', logistica_rev.get("logistica_reversa_es", ""),
                                                  "TextArea_ReserveLogisticES", callback_log, pendencias)
                        self.preencher_conferindo('//*[@id="b10-b17-b5-TextArea_ReserveLogisticPT"]', logistica_rev.get("logistica_reversa_pt", ""),
                                                  "TextArea_ReserveLogisticPT", callback_log, pendencias)
                    else:
                        self.safe_click('//*[@id="b10-b17-b5-DoesNotApply-input"]')
                except Exception as e:
                    _registrar_pendencia(pendencias, "na aba Descarte", e, callback_log)

                salvas["Descarte"] = self.safe_save_with_pause('//*[@id="b10-b17-$b5"]/div[5]/button', "Descarte", callback_log, callback_pause)

                # --- COMPLETO só com prova ------------------------------
                # "Ele só deve fazer isso se tiver certeza que preencheu os
                # campos de condições (salvo a parte da valorização)" -- pedido
                # do usuário, 2026-08-18.
                #
                # Antes esta linha era incondicional: bastava não estourar
                # exceção FATAL. Todos os 12 blocos de campos podiam ter
                # falhado, as 4 seções podiam não ter gravado, e a ficha saía
                # marcada como pronta. Planilha que diz COMPLETO no que ficou
                # pela metade é pior do que planilha vazia -- ninguém volta
                # para conferir o que está marcado como pronto.
                #
                # A Valorização fica de fora por definição: é seção de
                # Condições que este módulo não preenche, então não entra no
                # critério (é o "salvo a parte da valorização" do pedido).
                faltou_salvar = [s for s in SECOES_DE_CONDICOES if not salvas.get(s)]

                if pendencias or faltou_salvar:
                    if callback_log:
                        callback_log(f"{pmib}: INCOMPLETO -- o _STATUS_PMIB NÃO foi marcado.")
                        for item in pendencias:
                            callback_log(f"      - campo com falha: {item}")
                        for secao in faltou_salvar:
                            callback_log(f"      - seção sem confirmação de salvamento: {secao}")
                    lote_incompletas.append(pmib)
                else:
                    if callback_log: callback_log(f"{pmib} concluído no portal.")
                    self.atualizar_status_excel(caminho_status, pmib, "COMPLETO", callback_log, callback_ask)
                    lote_completas.append(pmib)

            except Exception as e:
                if callback_log: callback_log(f"!!! ERRO CRÍTICO processando {pmib}: {e} !!!")
                try:
                    self.engine.screenshot(f"erro_web_{pmib}.png")
                    if callback_log: callback_log(f"Evidência salva: erro_web_{pmib}.png")
                except Exception:
                    pass
                lote_incompletas.append(pmib)

        if callback_log:
            callback_log(
                f"\n=== Fim do lote: {len(lote_completas)} ficha(s) marcada(s) COMPLETO, "
                f"{len(lote_incompletas)} com pendência."
            )
            if lote_incompletas:
                callback_log("    Sem marcação no _STATUS_PMIB: " + ", ".join(lote_incompletas))
        return lote_completas, lote_incompletas

    def safe_save_with_pause(self, locator, section_name, callback_log=None, callback_pause=None):
        """Salva a seção e **confere se o portal confirmou**. Devolve bool.

        O clique é o que sempre foi. O que muda (2026-08-18) é o que vem
        depois: em vez de um `time.sleep` fixo e fé, espera o toast do próprio
        portal ("As condições de armazenamento foram modificadas com
        sucesso!") e confere se ele é DESTA seção.

        Também é mais rápido no caso bom: a espera devolve assim que a
        mensagem casa, em vez de dormir o tempo cheio.

        O `PAUSA_SALVAMENTO` de sempre CONTINUA, e continua incondicional. A
        tentação era pulá-lo quando o toast confirma -- economizaria 4 s por
        ficha. Mas isso seria empacotar uma mudança de ritmo do RPA dentro de
        uma correção de correção: se o robô ficasse instável depois, não
        haveria como saber qual das duas mudanças causou. A conferência é
        aditiva; a velocidade se discute noutro dia, com o portal na frente.
        """
        try:
            if callback_log: callback_log(f"Salvando {section_name}...")
            self.safe_click(locator)
        except Exception:
            if callback_log: callback_log(f"Falha ao salvar {section_name}. Aguardando intervenção manual.")
            if callback_pause:
                callback_pause(section_name)  # Chama o Frontend para mostrar a janela e pausar
            else:
                time.sleep(PAUSA_FALLBACK_SALVAMENTO)  # Fallback caso falte o callback
            return False

        # A conferência vem ANTES da pausa: o toast "aparece relativamente
        # rápido" e some depois, então dormir primeiro é arriscar perdê-lo.
        confirmou, _mensagem = self.portal.esperar_confirmacao_de_salvamento(
            section_name, callback_log=callback_log)
        time.sleep(PAUSA_SALVAMENTO)
        return confirmou

    def atualizar_status_excel(self, caminho, pmib, status, callback_log=None, callback_ask=None):
        """Atualiza o Excel com loop de retentativa caso esteja aberto.

        CP 1.3: cabeçalho/linha/marcação delegam para
        `core.excel.status_sheet.StatusPMIB`; o retry de `PermissionError`
        (variante INTERATIVA do diagnóstico -- ver `core.excel.locking`)
        delega para `locking.save_with_retry` via `StatusPMIB.salvar`.

        NOTA DE COMPORTAMENTO (ver docs/refatoracao/PENDENCIAS.md): o laço
        original recarregava o workbook INTEIRO (e reaplicava a busca de
        cabeçalho/edição de célula) a cada retentativa, dentro do próprio
        `while True`. Aqui o workbook é carregado e a célula marcada UMA
        única vez; só o `wb.save(caminho)` retenta. Equivalente no cenário
        real (usuário fecha o Excel e clica "tentar novamente"); a
        diferença é só teórica.
        """
        pmib_alvo = str(pmib).strip()

        try:
            painel = status_sheet.StatusPMIB(caminho, config.ABA_LISTA_MATERIAIS)
            # 1. Busca dinâmica de Cabeçalho (Varre as 15 primeiras linhas,
            #    49 colunas) -- mesmo alcance do original.
            painel.abrir(
                keywords={config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB, config.COL_CONDICOES: config.COL_CONDICOES},
                max_row=15,
                max_col=49,
            )

            # Fallback caso não encontre os nomes exatos (mesmas colunas
            # fixas 8/10 do original).
            painel.col_map.setdefault(config.COL_CODIGO_PMIB, 8)
            painel.col_map.setdefault(config.COL_CONDICOES, 10)
            header_row = painel.header_row if painel.header_row is not None else 1

            # 2. Busca varrendo da linha do cabeçalho pra baixo -- 3.
            #    Blindagem contra Perda de Precisão (o segredo do .1165)
            #    via `pmib_codes.normalize_pmib` (dentro de `buscar_linha`).
            linha = painel.buscar_linha(pmib_alvo, header_row=header_row)

            if linha is not None:
                # 4. Grava o status.
                painel.marcar_linha(linha, {config.COL_CONDICOES: True}, valor=status)

                def _on_locked(attempt, exc):
                    if callback_log:
                        callback_log("Erro: Arquivo Excel aberto.")
                    if callback_ask:
                        # Envia a requisição para a UI perguntando o que
                        # fazer e aguarda resposta.
                        resposta_retry = callback_ask("ARQUIVO_BLOQUEADO")
                        if not resposta_retry:
                            if callback_log:
                                callback_log("Salvamento ignorado pelo usuário.")
                        return bool(resposta_retry)
                    return False  # Fallback: sem callback_ask, não retenta.

                try:
                    painel.salvar(on_locked=_on_locked)
                except PermissionError:
                    # Usuário optou por não retentar (ou não havia
                    # callback_ask) -- já logado em `_on_locked` acima.
                    painel.fechar()
                    return

                if callback_log:
                    callback_log(f"Excel atualizado para COMPLETO: {pmib_alvo}")
            else:
                if callback_log:
                    callback_log(f"Aviso Crítico: PMIB {pmib_alvo} NÃO encontrado na planilha _STATUS. (Não pôde salvar).")

            painel.fechar()

        except Exception as e:
            if callback_log:
                callback_log(f"Erro ao atualizar Excel: {e}")
