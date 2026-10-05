# -*- coding: utf-8 -*-
"""
Regras de negocio e leitura das planilhas de sobressalentes.

Fonte unica das regras usadas pelos scripts do cofre (prototipo de dashboard,
migracao do _STATUS_PMIB v2) e REFERENCIA para o Power Query / DAX do Power BI
(`_gestao_v2/powerbi/`). Se uma regra mudar aqui, mude la tambem.

REGRA INEGOCIAVEL: este modulo **so le** o Box. Nenhuma funcao daqui escreve
em disco.

Requisitos: openpyxl, pandas
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import re
import unicodedata
import warnings

import openpyxl
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# --------------------------------------------------------------------------
# Caminhos
# --------------------------------------------------------------------------
BOX = pathlib.Path.home() / "Box" / "CMI - Consórcio Itaipu" / "11 - Ger. Engenharia" / "15 - PDM"
PASTA_PMIB = BOX / "SOBRESSALENTES - PMIB"
MAPEADORA = PASTA_PMIB / "Mapeamento Listas de Sobressalentes.xlsx"

# Pastas e arquivos que nao sao controle vivo (copias, testes, backups, comentarios do Aconex)
IGNORAR_PASTAS = ("00 - OBSOLETO", "10- TESTES", "TESTES_AUTOSPEC", "\\DATASHEETS\\", "BACKUP", "OBSOLETO")
IGNORAR_ARQUIVOS = ("~$", " - COPY", "- CÓPIA", "COPIA", "COMENT", "RESPOSTA")

# --------------------------------------------------------------------------
# Prazos
# --------------------------------------------------------------------------
PRAZO_AUTORIZACAO_DU = 15      # dias uteis para Itaipu autorizar a entrega (antes: 14 dias corridos)
LMR_ATENCAO_DIAS = 60          # compromisso CMI: Aplicacao LMR em 2 a 3 meses do e-mail de intencao
LMR_LIMITE_DIAS = 90

# Feriados nacionais do Brasil + pontos facultativos de Carnaval e Corpus Christi.
# DECISAO EM ABERTO: confirmar com Itaipu qual calendario vale para os 15 d.u.
# (BR, PY, municipal de Foz). Para tirar uma data, apague a linha.
FERIADOS: dict[dt.date, str] = {
    dt.date(2024, 1, 1): "Confraternização Universal",
    dt.date(2024, 2, 12): "Carnaval (ponto facultativo)",
    dt.date(2024, 2, 13): "Carnaval (ponto facultativo)",
    dt.date(2024, 3, 29): "Sexta-feira Santa",
    dt.date(2024, 4, 21): "Tiradentes",
    dt.date(2024, 5, 1): "Dia do Trabalho",
    dt.date(2024, 5, 30): "Corpus Christi (ponto facultativo)",
    dt.date(2024, 9, 7): "Independência",
    dt.date(2024, 10, 12): "Nossa Senhora Aparecida",
    dt.date(2024, 11, 2): "Finados",
    dt.date(2024, 11, 15): "Proclamação da República",
    dt.date(2024, 11, 20): "Consciência Negra",
    dt.date(2024, 12, 25): "Natal",
    dt.date(2025, 1, 1): "Confraternização Universal",
    dt.date(2025, 3, 3): "Carnaval (ponto facultativo)",
    dt.date(2025, 3, 4): "Carnaval (ponto facultativo)",
    dt.date(2025, 4, 18): "Sexta-feira Santa",
    dt.date(2025, 4, 21): "Tiradentes",
    dt.date(2025, 5, 1): "Dia do Trabalho",
    dt.date(2025, 6, 19): "Corpus Christi (ponto facultativo)",
    dt.date(2025, 9, 7): "Independência",
    dt.date(2025, 10, 12): "Nossa Senhora Aparecida",
    dt.date(2025, 11, 2): "Finados",
    dt.date(2025, 11, 15): "Proclamação da República",
    dt.date(2025, 11, 20): "Consciência Negra",
    dt.date(2025, 12, 25): "Natal",
    dt.date(2026, 1, 1): "Confraternização Universal",
    dt.date(2026, 2, 16): "Carnaval (ponto facultativo)",
    dt.date(2026, 2, 17): "Carnaval (ponto facultativo)",
    dt.date(2026, 4, 3): "Sexta-feira Santa",
    dt.date(2026, 4, 21): "Tiradentes",
    dt.date(2026, 5, 1): "Dia do Trabalho",
    dt.date(2026, 6, 4): "Corpus Christi (ponto facultativo)",
    dt.date(2026, 9, 7): "Independência",
    dt.date(2026, 10, 12): "Nossa Senhora Aparecida",
    dt.date(2026, 11, 2): "Finados",
    dt.date(2026, 11, 15): "Proclamação da República",
    dt.date(2026, 11, 20): "Consciência Negra",
    dt.date(2026, 12, 25): "Natal",
    dt.date(2027, 1, 1): "Confraternização Universal",
    dt.date(2027, 2, 8): "Carnaval (ponto facultativo)",
    dt.date(2027, 2, 9): "Carnaval (ponto facultativo)",
    dt.date(2027, 3, 26): "Sexta-feira Santa",
    dt.date(2027, 4, 21): "Tiradentes",
    dt.date(2027, 5, 1): "Dia do Trabalho",
    dt.date(2027, 5, 27): "Corpus Christi (ponto facultativo)",
    dt.date(2027, 9, 7): "Independência",
    dt.date(2027, 10, 12): "Nossa Senhora Aparecida",
    dt.date(2027, 11, 2): "Finados",
    dt.date(2027, 11, 15): "Proclamação da República",
    dt.date(2027, 11, 20): "Consciência Negra",
    dt.date(2027, 12, 25): "Natal",
    dt.date(2028, 1, 1): "Confraternização Universal",
    dt.date(2028, 2, 28): "Carnaval (ponto facultativo)",
    dt.date(2028, 2, 29): "Carnaval (ponto facultativo)",
    dt.date(2028, 4, 14): "Sexta-feira Santa",
    dt.date(2028, 4, 21): "Tiradentes",
    dt.date(2028, 5, 1): "Dia do Trabalho",
    dt.date(2028, 6, 15): "Corpus Christi (ponto facultativo)",
    dt.date(2028, 9, 7): "Independência",
    dt.date(2028, 10, 12): "Nossa Senhora Aparecida",
    dt.date(2028, 11, 2): "Finados",
    dt.date(2028, 11, 15): "Proclamação da República",
    dt.date(2028, 11, 20): "Consciência Negra",
    dt.date(2028, 12, 25): "Natal",
}


def dia_util(d: dt.date) -> bool:
    return d.weekday() < 5 and d not in FERIADOS


def somar_dias_uteis(inicio: dt.date, n: int) -> dt.date:
    """Equivale ao WORKDAY(inicio; n; Feriados) do Excel."""
    d = inicio
    while n > 0:
        d += dt.timedelta(days=1)
        if dia_util(d):
            n -= 1
    return d


def dias_uteis_entre(de: dt.date, ate: dt.date) -> int:
    """Dias uteis no intervalo (de, ate]. Zero se ate <= de."""
    if ate <= de:
        return 0
    return sum(1 for i in range(1, (ate - de).days + 1) if dia_util(de + dt.timedelta(days=i)))


# --------------------------------------------------------------------------
# Normalizacao
# --------------------------------------------------------------------------
def normalizar(valor) -> str:
    """Maiusculas, sem acento, espacos colapsados. None/NaN -> ''."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    s = unicodedata.normalize("NFD", str(valor)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.upper()).strip()


def normalizar_pmib(valor) -> str | None:
    """
    '4500063671.0156', 4500063671.0156 (numero), '45000636710156' -> '4500063671.0156'.
    Sequencial com 3 digitos perdeu o zero do FIM na conversao numerica — completa
    a direita, como o SIG-FT (`ljust`). Qualquer outra coisa -> None.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float)):
        s = f"{valor:.4f}"
    else:
        s = re.sub(r"\s", "", str(valor))
    m = re.fullmatch(r"4500063671\.?(\d{1,4})", s)
    if not m:
        return None
    seq = m.group(1)
    if "." not in s and len(seq) != 4:
        return None
    return f"4500063671.{seq.ljust(4, '0')}"


STATUS_CANONICO = {
    "INICIAR": "INICIAR",
    "FICHA CRIADA": "FICHA CRIADA",
    "FICHAS CRIADAS": "FICHA CRIADA",
    "COM O FORNECEDOR": "COM O FORNECEDOR",
    "EM ELABORACAO": "EM ELABORAÇÃO",
    "EM ANALISE IB": "EM ANÁLISE IB",
    "EM ANALISE ITAIPU": "EM ANÁLISE IB",
    "EM CORRECAO": "EM CORREÇÃO",
    "APROVADO": "APROVADO",
    "DUPLICADO": "DUPLICADO",
    "N/A": "N/A",
}
ORDEM_ETAPA = ["INICIAR", "FICHA CRIADA", "COM O FORNECEDOR", "EM ELABORAÇÃO",
               "EM CORREÇÃO", "EM ANÁLISE IB", "APROVADO"]
STATUS_EMITIDA = {"EM ANÁLISE IB", "EM CORREÇÃO", "APROVADO"}

# Com quem esta a acao — a leitura que interessa numa reuniao com o cliente
COM_QUEM = {
    "INICIAR": "CMI",
    "FICHA CRIADA": "CMI",
    "EM ELABORAÇÃO": "CMI",
    "EM CORREÇÃO": "CMI",
    "COM O FORNECEDOR": "FORNECEDOR",
    "EM ANÁLISE IB": "ITAIPU",
    "APROVADO": "CONCLUÍDO",
}

TIPO_CANONICO = {
    "FISICA E DOCUMENTAL": "FÍSICA E DOCUMENTAL",
    "FISICO E DOCUMENTAL": "FÍSICA E DOCUMENTAL",
    "DOCUMENTAL": "DOCUMENTAL",
    "APENAS DOCUMENTAL": "DOCUMENTAL",
    "TITULO": "TÍTULO",
    "CONJUNTO": "TÍTULO",
    "CONJUNTO (TITULO)": "TÍTULO",
}

SECOES = ["INFO. GERAIS", "CARACT. TECNICAS", "DOCUMENTOS E IMAGENS", "CONDICOES",
          "VALORIZACAO", "APLICACAO - LMR"]


def ignorado(caminho: pathlib.Path) -> bool:
    texto = normalizar(str(caminho)).replace("/", "\\")
    nome = normalizar(caminho.name)
    return (any(normalizar(p) in texto for p in IGNORAR_PASTAS)
            or any(normalizar(a) in nome for a in IGNORAR_ARQUIVOS))


# --------------------------------------------------------------------------
# Leitura generica: acha a linha de cabecalho pela palavra-chave
# --------------------------------------------------------------------------
def ler_tabela(caminho: pathlib.Path, aba: str, chave: str = "DESCRICAO", max_busca: int = 30,
               max_col: int = 60, max_vazias: int = 200) -> pd.DataFrame:
    """
    Le a aba a partir da linha cujo cabecalho contem `chave`. Cabecalhos normalizados.
    Leitura limitada (colunas e linhas vazias seguidas): planilha exportada com
    dimensao A1:XFD1048576 faria o openpyxl percorrer bilhoes de celulas.
    """
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    linhas, vazias = [], 0
    try:
        ws = wb[aba] if aba in wb.sheetnames else wb.worksheets[0]
        for r in ws.iter_rows(max_col=max_col, values_only=True):
            if any(v not in (None, "") for v in r):
                vazias = 0
            else:
                vazias += 1
                if vazias > max_vazias:
                    break
            linhas.append(r)
    finally:
        wb.close()
    pos = next((i for i, r in enumerate(linhas[:max_busca]) if any(normalizar(c) == chave for c in r)), None)
    if pos is None:
        return pd.DataFrame()
    cab, vistos = [], {}
    for j, c in enumerate(linhas[pos]):
        nome = normalizar(c) or f"_COL{j}"
        vistos[nome] = vistos.get(nome, 0) + 1
        cab.append(nome if vistos[nome] == 1 else f"{nome}_{vistos[nome]}")
    corpo = [r for r in linhas[pos + 1:] if any(v not in (None, "") for v in r)]
    return pd.DataFrame(corpo, columns=cab[:len(linhas[pos])])


def _para_data(v) -> dt.date | None:
    """Data real ou None. NaT/NaN/texto -> None (NaT e 'verdadeiro' em Python: cuidado)."""
    if v is None or v is pd.NaT or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.date()
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return None


# --------------------------------------------------------------------------
# Regras por item
# --------------------------------------------------------------------------
SITUACOES_AUTORIZACAO = ["AGUARDANDO ITAIPU", "ATRASADO ITAIPU", "AUTORIZADO"]


def _inteiro(v) -> int | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else int(f)                      # NaN != NaN


def situacao_autorizacao(data_email: dt.date | None, situacao_atual, entregue, hoje: dt.date,
                         dias_atual=None) -> tuple[str, dt.date | None, int | None]:
    """
    Devolve (situacao, prazo, dias_de_atraso) — o que o SIG-FT grava nas colunas
    SITUAÇÃO DA AUTORIZAÇÃO e DIAS DE ATRASO do _STATUS_PMIB (o prazo nao e gravado).

    ""                  sem e-mail de intencao (celula em branco)
    AGUARDANDO ITAIPU   e-mail enviado, dentro do prazo de 15 dias uteis
    ATRASADO ITAIPU     prazo vencido sem autorizacao; dias = dias CORRIDOS desde o prazo
    AUTORIZADO          Itaipu autorizou (export de autorizados; o antigo APTO = SIM; ou ja
                        entregue). DIAS DE ATRASO fica congelado no valor que tinha — o
                        atraso que houve ate a autorizacao (ver dias_de_atraso_na_autorizacao)
    """
    prazo = somar_dias_uteis(data_email, PRAZO_AUTORIZACAO_DU) if data_email else None
    if normalizar(situacao_atual) in ("AUTORIZADO", "SIM") or normalizar(entregue) == "SIM":
        return "AUTORIZADO", prazo, _inteiro(dias_atual)
    if prazo is None:
        return "", None, None
    if hoje > prazo:
        return "ATRASADO ITAIPU", prazo, (hoje - prazo).days
    return "AGUARDANDO ITAIPU", prazo, None


def dias_de_atraso_na_autorizacao(data_email: dt.date | None, data_autorizacao: dt.date) -> int | None:
    """Quando a autorizacao chega (data do export de autorizados): dias corridos alem do prazo,
    ou None se chegou no prazo. E o valor que fica congelado em DIAS DE ATRASO."""
    if not data_email:
        return None
    prazo = somar_dias_uteis(data_email, PRAZO_AUTORIZACAO_DU)
    return (data_autorizacao - prazo).days if data_autorizacao > prazo else None


def pendencia(e_ficha: bool, status: str, sit_aut: str, ok: dict[str, bool], apto: bool, entregue: bool,
              tipo: str) -> str:
    """
    A primeira coisa que falta para a ficha andar — o que vai para a fila de trabalho.
    Ficha ja emitida so tem tres pendencias possiveis do CMI: cobrar a autorizacao,
    entregar o material autorizado, ou a LMR que faltou. Secao sem COMPLETO numa ficha
    emitida e coluna desatualizada, nao trabalho.
    """
    if not e_ficha:
        return "—"
    if status == "EM CORREÇÃO":
        return "Responder comentários de Itaipu"
    if sit_aut == "ATRASADO ITAIPU":
        return "Cobrar autorização de Itaipu"
    if apto and not entregue and tipo == "FÍSICA E DOCUMENTAL":
        return "Entregar no almoxarifado"
    if status in STATUS_EMITIDA:
        return "Aplicação LMR" if (status != "APROVADO" and not ok["APLICACAO - LMR"]) else "—"
    fornecedor_ok = all(ok[s] for s in ("INFO. GERAIS", "CARACT. TECNICAS", "DOCUMENTOS E IMAGENS", "CONDICOES"))
    if status == "COM O FORNECEDOR" or not fornecedor_ok:
        return "Informações do fornecedor"
    if not ok["VALORIZACAO"]:
        return "Valorização"
    if not ok["APLICACAO - LMR"]:
        return "Aplicação LMR"
    return "Emitir para Itaipu"


def situacao_lmr(data_email: dt.date | None, lmr: str, hoje: dt.date) -> str:
    """Compromisso do CMI: Aplicacao LMR em ate 3 meses do e-mail de intencao."""
    if normalizar(lmr) == "COMPLETO":
        return "LMR CONCLUÍDA"
    if not data_email:
        return "SEM PEDIDO"
    dias = (hoje - data_email).days
    if dias > LMR_LIMITE_DIAS:
        return "LMR FORA DO COMPROMISSO"
    if dias > LMR_ATENCAO_DIAS:
        return "LMR EM ATENÇÃO"
    return "LMR NO PRAZO"


# --------------------------------------------------------------------------
# Leitores de alto nivel
# --------------------------------------------------------------------------
def listar_status_pmib(raiz: pathlib.Path = PASTA_PMIB) -> list[pathlib.Path]:
    return sorted(p for p in raiz.rglob("*_STATUS_PMIB.xlsx") if not ignorado(p.relative_to(raiz)))


def ler_listas_precos(raiz: pathlib.Path = PASTA_PMIB) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Le as listas de precos (`...PB021` vigente e `...PB020-0x` legado).
    Devolve (itens_por_pmib, arquivos). Para cada PMIB vale a melhor fonte:
    PB021 antes de PB020-0x; entre iguais, o arquivo modificado por ultimo.
    """
    candidatos = [p for ext in ("*.xlsm", "*.xlsx") for p in raiz.rglob(ext)
                  if re.search(r"PB021|PB020-0\d", p.name, re.I) and "STATUS_PMIB" not in p.name.upper()
                  and not ignorado(p.relative_to(raiz))]
    linhas, arquivos = [], []
    for p in candidatos:
        df = ler_tabela(p, "Lista de Materiais")
        if df.empty:
            continue
        codigo = re.sub(r"\[.*?\]", "", p.stem).strip()
        geracao = 2 if "PB021" in codigo.upper() else 1
        col_ge = next((c for c in ("CODIGO GE", "CODIGO GE (MTA)", "CODIGO CMI") if c in df.columns), None)
        df["PMIB"] = df.get("CODIGO PMIB", pd.Series(dtype=object)).map(normalizar_pmib)
        df["TIPO"] = [TIPO_CANONICO.get(normalizar(v)) for v in df.get("TIPO DE ENTREGA", pd.Series([None] * len(df)))]
        df["CODIGO_GE"] = df[col_ge] if col_ge else None
        df["VALOR_UNIT"] = pd.to_numeric(df.get("VALOR UNITARIO"), errors="coerce")
        df["ARQUIVO_PRECO"] = codigo
        df["GERACAO"] = geracao
        df["MTIME"] = p.stat().st_mtime
        linhas.append(df[["PMIB", "TIPO", "CODIGO_GE", "VALOR_UNIT", "ARQUIVO_PRECO", "GERACAO", "MTIME"]])
        arquivos.append({
            "ARQUIVO_PRECO": codigo, "PASTA": str(p.parent.relative_to(raiz)), "GERACAO": "PB021" if geracao == 2 else "PB020-0x (legado)",
            "LINHAS": len(df), "FICHAS": df["PMIB"].nunique(), "TEM_TIPO_ENTREGA": "TIPO DE ENTREGA" in df.columns,
            "VALOR_TOTAL_USD": float((pd.to_numeric(df.get("QTD."), errors="coerce").fillna(0) * df["VALOR_UNIT"].fillna(0)).sum()),
            "MODIFICADO": dt.datetime.fromtimestamp(p.stat().st_mtime).date().isoformat(),
        })
    if not linhas:
        return pd.DataFrame(columns=["PMIB"]), pd.DataFrame(arquivos)
    todos = pd.concat(linhas, ignore_index=True)
    todos = todos[todos["PMIB"].notna()].sort_values(["GERACAO", "MTIME"], ascending=False)
    return todos.drop_duplicates("PMIB").drop(columns=["MTIME"]), pd.DataFrame(arquivos)


def ler_mapeadora(caminho: pathlib.Path = MAPEADORA) -> dict[str, pd.DataFrame]:
    """Aba principal (uma linha por lista), Atividades e Follow-up das listas de precos."""
    out = {}
    listas = pd.read_excel(caminho, sheet_name="Acompanhamento Sobressalente", header=1, dtype=object).iloc[:, :35]
    listas.columns = [normalizar(c) for c in listas.columns]
    out["listas"] = listas[listas["N DOCUMENTO ITAIPU"].notna()].reset_index(drop=True)
    try:
        atv = pd.read_excel(caminho, sheet_name="Atividades", dtype=object)
        atv.columns = [normalizar(c) for c in atv.columns]
        atv["LISTA"] = atv["CODIGO ITAIPU"].where(atv["NV"] == 1).ffill()
        atv["GRUPO"] = atv["DESCRICAO"].where(atv["NV"] == 1).ffill()
        out["atividades"] = atv[atv["NV"] == 2].reset_index(drop=True)
    except ValueError:
        out["atividades"] = pd.DataFrame()
    try:
        fu = pd.read_excel(caminho, sheet_name="Lista de preços Follow-up", dtype=object)
        fu.columns = [normalizar(c) for c in fu.columns]
        out["precos_followup"] = fu[fu["N DOCUMENTO ITAIPU"].notna()].reset_index(drop=True)
    except ValueError:
        out["precos_followup"] = pd.DataFrame()
    return out


def ler_itens(raiz: pathlib.Path = PASTA_PMIB, hoje: dt.date | None = None,
              precos: pd.DataFrame | None = None) -> pd.DataFrame:
    """Uma linha por linha de material de todos os _STATUS_PMIB, com as regras aplicadas."""
    hoje = hoje or dt.date.today()
    frames = []
    for p in listar_status_pmib(raiz):
        df = ler_tabela(p, "Lista de Materiais")
        if df.empty or "DESCRICAO" not in df.columns:
            continue
        df = df[df["DESCRICAO"].map(normalizar) != ""].copy()
        rel = p.relative_to(raiz)
        df["LISTA"] = p.name[: -len("_STATUS_PMIB.xlsx")]
        df["AREA"] = rel.parts[0]
        df["SISTEMA"] = " › ".join(rel.parts[1:-1]) or rel.parts[0]
        df["ARQUIVO"] = str(rel)
        frames.append(df)
    itens = pd.concat(frames, ignore_index=True)
    for c in ["TIPO DE ENTREGA", "FORNECEDOR", "PROCUREMENT", "SITUACAO DA AUTORIZACAO", "DIAS DE ATRASO",
              "APTO PARA ENTREGA", "EQUIPAMENTO ENTREGUE", "CODIGO CMI", "MARCA/MODELO", *SECOES]:
        if c not in itens.columns:
            itens[c] = None
    # SITUACAO DA AUTORIZACAO substituiu APTO PARA ENTREGA (SIM -> AUTORIZADO); arquivo antigo cai no APTO
    itens["SITUACAO DA AUTORIZACAO"] = [s if normalizar(s) else a for s, a in
                                        zip(itens["SITUACAO DA AUTORIZACAO"], itens["APTO PARA ENTREGA"])]

    itens["PMIB"] = itens["CODIGO PMIB"].map(normalizar_pmib)
    itens["STATUS_N"] = itens["STATUS"].map(normalizar).map(lambda s: STATUS_CANONICO.get(s, "SEM STATUS" if not s else s))
    # STATUS DUPLICADO = o mesmo item repetido NA MESMA LISTA: a linha repete o PMIB de outra
    # linha e nao tem as secoes preenchidas. Nao e ficha nova (a ficha conta pela outra linha);
    # a QUANTIDADE dela conta. Ja a ficha duplicada DE OUTRO SISTEMA e ficha nova, com PMIB
    # proprio, PDM.9900.000 e o PMIB da original em OBSERVACOES — conta como ficha.
    itens["E_FICHA"] = itens["PMIB"].notna() & (itens["STATUS_N"] != "DUPLICADO")
    itens["DUP_OUTRO_SISTEMA"] = itens["PDM USADO"].map(normalizar).str.startswith("PDM.9900") if "PDM USADO" in itens else False
    itens["PMIB_ORIGINAL"] = [
        (normalizar_pmib(m.group(0)) if (m := re.search(r"4500063671\.?\d{3,4}", str(o or ""))) else None) if d else None
        for o, d in zip(itens["OBSERVACOES"] if "OBSERVACOES" in itens else [None] * len(itens), itens["DUP_OUTRO_SISTEMA"])]
    itens["COM_QUEM"] = itens["STATUS_N"].map(COM_QUEM).fillna("—")
    for s in SECOES:
        itens[f"OK_{s}"] = itens[s].map(normalizar).eq("COMPLETO")

    # Tipo de entrega: coluna do _STATUS_PMIB (v2) > lista de precos > nao classificado
    if precos is None:
        precos, _ = ler_listas_precos(raiz)
    por_pmib = {r.PMIB: r for r in precos.itertuples(index=False)} if len(precos) else {}
    tipo_status = [TIPO_CANONICO.get(normalizar(v)) for v in itens["TIPO DE ENTREGA"]]
    tipo_preco = [getattr(por_pmib.get(k), "TIPO", None) if k else None for k in itens["PMIB"]]
    tipo_preco = [t if isinstance(t, str) else None for t in tipo_preco]          # NaN e "verdadeiro": cuidado
    itens["TIPO_ENTREGA"] = [s or p or "NÃO CLASSIFICADO" for s, p in zip(tipo_status, tipo_preco)]
    itens["ORIGEM_TIPO"] = ["_STATUS_PMIB" if s else "LISTA DE PREÇOS" if p else "—" for s, p in zip(tipo_status, tipo_preco)]
    itens["VALOR_UNIT"] = [getattr(por_pmib.get(k), "VALOR_UNIT", None) if k else None for k in itens["PMIB"]]
    itens["CODIGO_GE_PRECO"] = [getattr(por_pmib.get(k), "CODIGO_GE", None) if k else None for k in itens["PMIB"]]
    itens["ARQUIVO_PRECO"] = [getattr(por_pmib.get(k), "ARQUIVO_PRECO", None) if k else None for k in itens["PMIB"]]
    itens["QTD"] = pd.to_numeric(itens["QTD."], errors="coerce")

    # Datas e situacoes — calculadas em listas Python puras: o pandas 3 converte
    # date/None em datetime64/NaT, e NaT e "verdadeiro" num `if`.
    dt_email = [_para_data(v) for v in itens["DATA DO EMAIL COMUNICANDO ENTREGA"]]
    itens["ENTREGUE"] = itens["EQUIPAMENTO ENTREGUE"].map(normalizar).eq("SIM")
    # a mesma regra que o SIG-FT grava: recalculada aqui para o painel nao depender de o SIG-FT ter rodado hoje
    sit = [situacao_autorizacao(e, s, n, hoje, d) for e, s, n, d in zip(
        dt_email, itens["SITUACAO DA AUTORIZACAO"], itens["EQUIPAMENTO ENTREGUE"], itens["DIAS DE ATRASO"])]
    itens["SITUACAO_AUT"] = [s[0] or "SEM PEDIDO" for s in sit]
    itens["APTO"] = itens["SITUACAO_AUT"].eq("AUTORIZADO")
    itens["PRAZO_AUT"] = pd.Series([s[1].isoformat() if s[1] else None for s in sit], index=itens.index, dtype=object)
    itens["DIAS_ATRASO"] = pd.Series([s[2] for s in sit], index=itens.index, dtype=object)
    itens["SITUACAO_LMR"] = [situacao_lmr(e, l, hoje) for e, l in zip(dt_email, itens["APLICACAO - LMR"])]
    itens["DIAS_DESDE_EMAIL"] = pd.Series([(hoje - e).days if e else None for e in dt_email], index=itens.index, dtype=object)
    itens["PENDENCIA"] = [
        pendencia(ef, st, sa, {s: bool(itens.at[i, f"OK_{s}"]) for s in SECOES}, ap, en, tp)
        for i, ef, st, sa, ap, en, tp in zip(itens.index, itens["E_FICHA"], itens["STATUS_N"], itens["SITUACAO_AUT"],
                                              itens["APTO"], itens["ENTREGUE"], itens["TIPO_ENTREGA"])]
    itens["DT_EMAIL"] = pd.Series([e.isoformat() if e else None for e in dt_email], index=itens.index, dtype=object)
    return itens
