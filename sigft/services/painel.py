r"""
sigft/services/painel.py — o painel HTML de sobressalentes, gerado pelo Gestão PMIB.

T7 do roteiro "Gestão PMIB no tratamento v2" (`gestao-sobressalentes/07 -
Diagnostico/Tarefa SIG-FT - Calculo e Gravacao sem Perda.md`). Porte de
`gestao-sobressalentes/_scripts/gerar_prototipo_dashboard.py` e da parte de
leitura e regras de `regras_sobressalentes.py` -- é para portar, não importar:
o cofre é material de referência, não código do app.

Papel do painel e a regra de ouro
---------------------------------
O **Power BI v2 é o painel oficial**, inclusive para Itaipu. Este HTML é a
FOTO DO DIA para quem não tem Power BI: um arquivo só, que abre no navegador e
não depende de rede (a rede do trabalho bloqueia CDN; o template não usa nada
externo). **Os números têm de ser os mesmos do Power BI** -- ficha = PMIB
distinto; material entregue = itens físicos entregues; filtros por
Especificação técnica e Capítulo. Por isso nenhuma regra nem definição muda
aqui: mudança vale para os dois painéis (registrar em PENDENCIAS e avisar o
Luan).

De onde vem cada coisa
----------------------
  - a regra da autorização: `services/autorizacao.py` -- a MESMA que o Gestão
    PMIB usa para gravar; nunca duplicada aqui;
  - quais `_STATUS_PMIB` contam: `services/status_pmib_arquivos.py` -- as
    mesmas exclusões de pasta/cópia do Gestão PMIB (T3-a);
  - o desenho: `sigft/assets/painel_template.html`, CÓPIA SEM MUDANÇA do
    protótipo do cofre; os dados entram em `<script id="dados">`.

Conferência: `gestao-sobressalentes/_gestao_v2/validar_painel.py` compara os
dados embutidos com os da referência, no kit de teste, campo a campo --
`tests/test_painel.py` o roda (PAINEL OK).

O pandas é real no app e dublê na suíte de testes: as funções puras (nomes,
datas, `limpar`) têm teste próprio; o resto é provado pelo validador.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import pathlib
import re
import sys
import warnings
import zipfile

import pandas as pd

from sigft.core.aconex import status_real
from sigft.services import autorizacao, status_pmib_arquivos

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

NOME_DO_ARQUIVO = "Painel de Sobressalentes.html"
NOME_DO_TEMPLATE = "painel_template.html"

normalizar = autorizacao.normalizar

# Compromisso do CMI: Aplicação LMR em 2 a 3 meses do e-mail de intenção.
LMR_ATENCAO_DIAS = 60
LMR_LIMITE_DIAS = 90

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
STATUS_EMITIDA = {"EM ANÁLISE IB", "EM CORREÇÃO", "APROVADO"}

# Com quem está a ação -- a leitura que interessa numa reunião com o cliente.
COM_QUEM = {
    "INICIAR": "CMI",
    "FICHA CRIADA": "CMI",
    "EM ELABORAÇÃO": "CMI",
    "EM CORREÇÃO": "CMI",
    "COM O FORNECEDOR": "FORNECEDOR",
    "EM ANÁLISE IB": "ITAIPU",
    "APROVADO": "CONCLUÍDO",
}

SECOES = ["INFO. GERAIS", "CARACT. TECNICAS", "DOCUMENTOS E IMAGENS", "CONDICOES",
          "VALORIZACAO", "APLICACAO - LMR"]


# --------------------------------------------------------------------------
# PMIB, no sentido ESTRITO do painel
# --------------------------------------------------------------------------
def normalizar_pmib(valor) -> str | None:
    """'4500063671.0156', 4500063671.0156 (número), '45000636710156' ->
    '4500063671.0156'. Qualquer outra coisa -> `None`.

    NÃO é o `pmib_codes.normalize_pmib` do resto do app, de propósito: aquele
    devolve o texto limpo de qualquer coisa; este decide O QUE É FICHA (PMIB
    válido, não DUPLICADO) -- a mesma definição do `fxPMIB` do Power BI. Trocar
    um pelo outro mudaria a contagem de fichas dos dois painéis.
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


# --------------------------------------------------------------------------
# Leitura
# --------------------------------------------------------------------------
def ler_tabela(caminho, aba: str, chave: str = "DESCRICAO", max_busca: int = 30,
               max_col: int = 60, max_vazias: int = 200) -> pd.DataFrame:
    """A aba a partir da linha cujo cabeçalho contém `chave`, com os nomes de
    coluna normalizados. Leitura limitada (colunas e linhas vazias seguidas):
    planilha exportada com dimensão A1:XFD1048576 faria o openpyxl percorrer
    bilhões de células."""
    import openpyxl  # preguiçoso: a suíte troca pelo real só quando precisa

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


def arquivos_status_pmib(raiz: pathlib.Path) -> list[pathlib.Path]:
    """Os `_STATUS_PMIB.xlsx` VIVOS da pasta -- as mesmas exclusões do Gestão
    PMIB (`status_pmib_arquivos`), em ordem de caminho."""
    return sorted(pathlib.Path(c) for _codigo, c in status_pmib_arquivos.listar(raiz).vivos
                  if c.lower().endswith(".xlsx"))


def _ignorado(raiz: pathlib.Path, caminho: pathlib.Path) -> bool:
    return status_pmib_arquivos.motivo_para_ignorar(str(caminho.relative_to(raiz))) is not None


def ler_listas_precos(raiz: pathlib.Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """As listas de preços (`...PB021` vigente e `...PB020-0x` legado).
    Devolve (itens_por_pmib, arquivos). Para cada PMIB vale a melhor fonte:
    PB021 antes de PB020-0x; entre iguais, o arquivo modificado por último."""
    candidatos = [p for ext in ("*.xlsm", "*.xlsx") for p in raiz.rglob(ext)
                  if re.search(r"PB021|PB020-0\d", p.name, re.I) and "STATUS_PMIB" not in p.name.upper()
                  and not _ignorado(raiz, p)]
    linhas, arquivos = [], []
    for p in candidatos:
        df = ler_tabela(p, "Lista de Materiais")
        if df.empty:
            continue
        codigo = re.sub(r"\[.*?\]", "", p.stem).strip()
        geracao = 2 if "PB021" in codigo.upper() else 1
        col_ge = next((c for c in ("CODIGO GE", "CODIGO GE (MTA)", "CODIGO CMI") if c in df.columns), None)
        df["PMIB"] = df.get("CODIGO PMIB", pd.Series(dtype=object)).map(normalizar_pmib)
        df["TIPO"] = [autorizacao.tipo_canonico(v) for v in df.get("TIPO DE ENTREGA", pd.Series([None] * len(df)))]
        df["CODIGO_GE"] = df[col_ge] if col_ge else None
        df["VALOR_UNIT"] = pd.to_numeric(df.get("VALOR UNITARIO"), errors="coerce")
        df["ARQUIVO_PRECO"] = codigo
        df["GERACAO"] = geracao
        df["MTIME"] = p.stat().st_mtime
        linhas.append(df[["PMIB", "TIPO", "CODIGO_GE", "VALOR_UNIT", "ARQUIVO_PRECO", "GERACAO", "MTIME"]])
        arquivos.append({
            "ARQUIVO_PRECO": codigo, "PASTA": str(p.parent.relative_to(raiz)),
            "GERACAO": "PB021" if geracao == 2 else "PB020-0x (legado)",
            "LINHAS": len(df), "FICHAS": df["PMIB"].nunique(), "TEM_TIPO_ENTREGA": "TIPO DE ENTREGA" in df.columns,
            "VALOR_TOTAL_USD": float((pd.to_numeric(df.get("QTD."), errors="coerce").fillna(0)
                                      * df["VALOR_UNIT"].fillna(0)).sum()),
            "MODIFICADO": dt.datetime.fromtimestamp(p.stat().st_mtime).date().isoformat(),
        })
    if not linhas:
        return pd.DataFrame(columns=["PMIB"]), pd.DataFrame(arquivos)
    todos = pd.concat(linhas, ignore_index=True)
    todos = todos[todos["PMIB"].notna()].sort_values(["GERACAO", "MTIME"], ascending=False)
    return todos.drop_duplicates("PMIB").drop(columns=["MTIME"]), pd.DataFrame(arquivos)


def ler_mapeadora(caminho) -> dict[str, pd.DataFrame]:
    """Aba principal (uma linha por lista), Atividades e Follow-up das listas de preços."""
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
    except (ValueError, KeyError):
        # Sem a aba (ValueError) ou com OUTRAS colunas (KeyError em NV,
        # CODIGO ITAIPU ou DESCRICAO): o painel sai sem a seção de atividades.
        out["atividades"] = pd.DataFrame()
    try:
        fu = pd.read_excel(caminho, sheet_name="Lista de preços Follow-up", dtype=object)
        fu.columns = [normalizar(c) for c in fu.columns]
        out["precos_followup"] = fu[fu["N DOCUMENTO ITAIPU"].notna()].reset_index(drop=True)
    except ValueError:
        out["precos_followup"] = pd.DataFrame()
    return out


# --------------------------------------------------------------------------
# Regras por item (além da autorização, que é do `autorizacao`)
# --------------------------------------------------------------------------
def pendencia(e_ficha: bool, status: str, sit_aut: str, ok: dict[str, bool], apto: bool, entregue: bool,
              tipo: str) -> str:
    """A primeira coisa que falta para a ficha andar -- o que vai para a fila de
    trabalho. Ficha já emitida só tem três pendências possíveis do CMI: cobrar
    a autorização, entregar o material autorizado, ou a LMR que faltou."""
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


def situacao_lmr(data_email: dt.date | None, lmr, hoje: dt.date) -> str:
    """Compromisso do CMI: Aplicação LMR em até 3 meses do e-mail de intenção."""
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


def _autorizacao_do_item(data_email, situacao, entregue, hoje, dias, tipo, status):
    """(situação, prazo, dias) para o painel. A regra é a do `autorizacao`; o
    prazo só é mostrado onde ele corre ou correu."""
    sit, dias_atraso = autorizacao.situacao_autorizacao(data_email, situacao, entregue, hoje, dias, tipo, status)
    prazo = None
    if sit in (autorizacao.AUTORIZADO, autorizacao.ATRASADO, autorizacao.AGUARDANDO):
        prazo = autorizacao.prazo_autorizacao(data_email)
    return sit, prazo, dias_atraso


def ler_itens(raiz: pathlib.Path, hoje: dt.date, precos: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por linha de material de todos os `_STATUS_PMIB`, com as regras aplicadas."""
    frames = []
    for p in arquivos_status_pmib(raiz):
        df = ler_tabela(p, "Lista de Materiais")
        if df.empty or "DESCRICAO" not in df.columns:
            continue
        df = df[df["DESCRICAO"].map(normalizar) != ""].copy()
        rel = p.relative_to(raiz)
        df["LISTA"] = status_pmib_arquivos.codigo_do_arquivo(p.name)
        df["AREA"] = rel.parts[0]
        df["SISTEMA"] = " › ".join(rel.parts[1:-1]) or rel.parts[0]
        df["ARQUIVO"] = str(rel)
        frames.append(df)
    if not frames:
        raise ValueError(f"nenhum _STATUS_PMIB legível em {raiz}")
    itens = pd.concat(frames, ignore_index=True)
    for c in ["TIPO DE ENTREGA", "FORNECEDOR", "PROCUREMENT", "SITUACAO DA AUTORIZACAO", "DIAS DE ATRASO",
              "APTO PARA ENTREGA", "EQUIPAMENTO ENTREGUE", "CODIGO CMI", "MARCA/MODELO", *SECOES]:
        if c not in itens.columns:
            itens[c] = None
    # SITUAÇÃO DA AUTORIZAÇÃO substituiu APTO PARA ENTREGA (SIM -> AUTORIZADO); arquivo antigo cai no APTO
    itens["SITUACAO DA AUTORIZACAO"] = [s if normalizar(s) else a for s, a in
                                        zip(itens["SITUACAO DA AUTORIZACAO"], itens["APTO PARA ENTREGA"])]

    itens["PMIB"] = itens["CODIGO PMIB"].map(normalizar_pmib)
    itens["STATUS_N"] = itens["STATUS"].map(normalizar).map(
        lambda s: STATUS_CANONICO.get(s, "SEM STATUS" if not s else s))
    # STATUS DUPLICADO = o mesmo item repetido NA MESMA LISTA: não é ficha nova
    # (a ficha conta pela outra linha); a QUANTIDADE dela conta. Já a ficha
    # duplicada DE OUTRO SISTEMA é ficha nova, com PMIB próprio, PDM.9900.000 e
    # o PMIB da original em OBSERVAÇÕES -- conta como ficha.
    itens["E_FICHA"] = itens["PMIB"].notna() & (itens["STATUS_N"] != "DUPLICADO")
    itens["DUP_OUTRO_SISTEMA"] = (itens["PDM USADO"].map(normalizar).str.startswith("PDM.9900")
                                  if "PDM USADO" in itens else False)
    itens["PMIB_ORIGINAL"] = [
        (normalizar_pmib(m.group(0)) if (m := re.search(r"4500063671\.?\d{3,4}", str(o or ""))) else None) if d else None
        for o, d in zip(itens["OBSERVACOES"] if "OBSERVACOES" in itens else [None] * len(itens),
                        itens["DUP_OUTRO_SISTEMA"])]
    itens["COM_QUEM"] = itens["STATUS_N"].map(COM_QUEM).fillna("—")
    for s in SECOES:
        itens[f"OK_{s}"] = itens[s].map(normalizar).eq("COMPLETO")

    # Tipo de entrega: coluna do _STATUS_PMIB (v2) > lista de preços > não classificado
    por_pmib = {r.PMIB: r for r in precos.itertuples(index=False)} if len(precos) else {}
    tipo_status = [autorizacao.tipo_canonico(v) for v in itens["TIPO DE ENTREGA"]]
    tipo_preco = [getattr(por_pmib.get(k), "TIPO", None) if k else None for k in itens["PMIB"]]
    tipo_preco = [t if isinstance(t, str) else None for t in tipo_preco]          # NaN é "verdadeiro": cuidado
    itens["TIPO_ENTREGA"] = [s or p or "NÃO CLASSIFICADO" for s, p in zip(tipo_status, tipo_preco)]
    itens["ORIGEM_TIPO"] = ["_STATUS_PMIB" if s else "LISTA DE PREÇOS" if p else "—"
                            for s, p in zip(tipo_status, tipo_preco)]
    itens["VALOR_UNIT"] = [getattr(por_pmib.get(k), "VALOR_UNIT", None) if k else None for k in itens["PMIB"]]
    itens["CODIGO_GE_PRECO"] = [getattr(por_pmib.get(k), "CODIGO_GE", None) if k else None for k in itens["PMIB"]]
    itens["ARQUIVO_PRECO"] = [getattr(por_pmib.get(k), "ARQUIVO_PRECO", None) if k else None for k in itens["PMIB"]]
    itens["QTD"] = pd.to_numeric(itens["QTD."], errors="coerce")

    # Datas e situações -- em listas Python puras: o pandas 3 converte
    # date/None em datetime64/NaT, e NaT é "verdadeiro" num `if`.
    dt_email = [autorizacao.para_data(v) for v in itens["DATA DO EMAIL COMUNICANDO ENTREGA"]]
    itens["ENTREGUE"] = itens["EQUIPAMENTO ENTREGUE"].map(normalizar).eq("SIM")
    # A mesma regra que o Gestão PMIB grava, recalculada aqui para o painel não
    # depender de o Gestão PMIB ter rodado hoje. O TIPO é o da coluna do
    # _STATUS_PMIB (o mesmo que a gravação usa); linha DUPLICADO não
    # autorizada fica em branco, como no arquivo.
    sit = [_autorizacao_do_item(e, s, n, hoje, d, t, st) for e, s, n, d, t, st in zip(
        dt_email, itens["SITUACAO DA AUTORIZACAO"], itens["EQUIPAMENTO ENTREGUE"], itens["DIAS DE ATRASO"],
        itens["TIPO DE ENTREGA"], itens["STATUS_N"])]
    tipo_col = [autorizacao.tipo_canonico(t) for t in itens["TIPO DE ENTREGA"]]
    itens["SITUACAO_AUT"] = [s[0] or ("SEM PEDIDO" if t == "FÍSICA E DOCUMENTAL" or st == "DUPLICADO"
                                      else "SEM TIPO DE ENTREGA")
                             for s, t, st in zip(sit, tipo_col, itens["STATUS_N"])]
    itens["APTO"] = itens["SITUACAO_AUT"].eq("AUTORIZADO")
    itens["PRAZO_AUT"] = pd.Series([s[1].isoformat() if s[1] else None for s in sit], index=itens.index, dtype=object)
    itens["DIAS_ATRASO"] = pd.Series([s[2] for s in sit], index=itens.index, dtype=object)
    itens["SITUACAO_LMR"] = [situacao_lmr(e, lmr, hoje) for e, lmr in zip(dt_email, itens["APLICACAO - LMR"])]
    itens["DIAS_DESDE_EMAIL"] = pd.Series([(hoje - e).days if e else None for e in dt_email],
                                          index=itens.index, dtype=object)
    itens["PENDENCIA"] = [
        pendencia(ef, st, sa, {s: bool(itens.at[i, f"OK_{s}"]) for s in SECOES}, ap, en, tp)
        for i, ef, st, sa, ap, en, tp in zip(itens.index, itens["E_FICHA"], itens["STATUS_N"], itens["SITUACAO_AUT"],
                                              itens["APTO"], itens["ENTREGUE"], itens["TIPO_ENTREGA"])]
    itens["DT_EMAIL"] = pd.Series([e.isoformat() if e else None for e in dt_email], index=itens.index, dtype=object)
    return itens


# --------------------------------------------------------------------------
# Nomes de exibição
# --------------------------------------------------------------------------
def iso(v) -> str | None:
    # `pd.Timestamp` é um `datetime`; o `NaT` também -- e é diferente de si mesmo.
    if isinstance(v, dt.datetime):
        return None if v != v else v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, str) and re.fullmatch(r"\d{2}/\d{2}/\d{4}", v.strip()):
        d, m, a = v.strip().split("/")
        return f"{a}-{m}-{d}"
    return None


GENERICAS = {"PARTE DIGITAL", "PARTE HIDRÁULICA", "PARTE MECÂNICA", "PAINEIS", "AR-ÁGUA DO GERADOR", "HPU DA COMPORTA",
             "INDICADOR DE POSIÇÃO", "BYPASS"}
ABREVIACOES = [
    (r"\s*[-–]\s*50\s*H[zZ]\s*[eE]\s*60\s*H[zZ]", ""),
    (r"SERVIÇOS AUXILIARES ESSENCIAIS", "SERV. AUX. ESSENCIAIS"),
    (r"REGULAÇÃO VEL E POT", "REGULAÇÃO DE VELOCIDADE"),
    (r"AUXILIARES A UG", "AUX. DA UG"),
    (r"SISTEMA DE AERAÇÃO AXIAL DA TURBINA", "AERAÇÃO AXIAL"),
    (r"SISTEMA DE VENTILAÇÃO DAS SALAS DE BATERIAS", "VENTILAÇÃO SALAS DE BATERIAS"),
    (r"SISTEMA DE VENTILAÇÃO E EXAUSTÃO PARA SALA GD", "VENTILAÇÃO E EXAUSTÃO SALA GD"),
    (r"SISTEMA DE ALIMENTAÇÃO ELÉTRICA DA UNIDADE", "ALIMENTAÇÃO ELÉTRICA DA UG"),
    (r"TRANSFORMADORES ELEVADORES PRINCIPAIS", "TRAFOS ELEVADORES"),
    (r"TRANSFORMADORES AUXILIARES À ÓLEO", "TRAFOS AUX. A ÓLEO"),
]


def sem_prefixo(area: str) -> str:
    """'05 - UNIDADE GERADORA' -> 'UNIDADE GERADORA'."""
    return re.sub(r"^\d+\s*-\s*", "", area or "")


def nome_exibicao(sistema: str) -> str:
    """Nome curto para gráfico: a última pasta, com a de cima quando a última
    sozinha não diz nada."""
    partes = []
    for p in sistema.split(" › "):
        if re.fullmatch(r"R\d+[A-Z]?", p):          # pasta de revisão (R0A) não é nome
            continue
        p = re.sub(r"^\d+-", "", sem_prefixo(p))
        for de, para in ABREVIACOES:
            p = re.sub(de, para, p)
        partes.append(p.strip())
    if not partes:
        return sistema
    ult = partes[-1]
    if len(partes) >= 2 and (ult.upper() in GENERICAS or len(ult) <= 14):
        return f"{partes[-2]} › {ult}"
    return ult


def nome_curto(descricao: str | None, lista: str) -> str:
    d = descricao or lista
    for lixo in ("ATUALIZAÇÃO TECNOLÓGICA - PAT_OBJ1 - ", "ATUALIZAÇÃO TECNOLÓGICA – PAT_OBJ1 - ", "ENG. ELÉTRICA - ",
                 "ENG. MECÂNICA  - ", "ENG. MECÂNICA - ", "ENG. ELETRÔNICA - ", " - LISTA DE SOBRESSALENTES"):
        d = d.replace(lixo, "")
    return d.strip()[:70]


# --------------------------------------------------------------------------
# Os dados do painel
# --------------------------------------------------------------------------
def montar(hoje: dt.date, raiz, mapeadora, callback_log=None) -> dict:
    """Os dados que vão dentro da página: fichas, listas, listas de preços,
    atividades e achados de qualidade."""
    raiz = pathlib.Path(raiz)

    def _log(msg):
        if callback_log:
            callback_log(msg)

    _log(" -> Painel: lendo as listas de preços...")
    precos, arquivos_preco = ler_listas_precos(raiz)
    _log(" -> Painel: lendo os _STATUS_PMIB...")
    itens = ler_itens(raiz, hoje, precos)
    _log(" -> Painel: lendo a planilha de mapeamento...")
    mapa = ler_mapeadora(mapeadora)
    listas_m = mapa["listas"]

    # procurement por lista (mapeadora), usado enquanto a coluna do _STATUS_PMIB v2 estiver vazia
    proc_lista = {str(lst).strip(): (p if isinstance(p, str) else None)
                  for lst, p in zip(listas_m["N DOCUMENTO ITAIPU"], listas_m["PROCUREMENT"])}

    # ---------------- fichas (lista|PMIB) ----------------
    # valor: TODAS as linhas da ficha, inclusive as DUPLICADO (repetição na mesma lista tem quantidade própria)
    com_pmib = itens[itens["PMIB"].notna()].copy()
    com_pmib["VALOR_LINHA"] = [q * v if (t == "FÍSICA E DOCUMENTAL" and pd.notna(q) and v is not None and pd.notna(v))
                               else 0.0
                               for q, v, t in zip(com_pmib["QTD"], com_pmib["VALOR_UNIT"], com_pmib["TIPO_ENTREGA"])]
    valor = com_pmib.groupby(["LISTA", "PMIB"])["VALOR_LINHA"].sum()
    # estado: a linha da ficha (a que não é DUPLICADO)
    f = itens[itens["E_FICHA"]].copy().drop_duplicates(["LISTA", "PMIB"])
    registros = []
    for r in f.itertuples(index=False):
        d = r._asdict()
        pc = d.get("PROCUREMENT")
        registros.append({
            "l": d["LISTA"], "a": sem_prefixo(d["AREA"]), "s": nome_exibicao(d["SISTEMA"]), "p": d["PMIB"],
            "d": str(d["DESCRICAO"])[:90], "st": d["STATUS_N"], "q": d["COM_QUEM"], "t": d["TIPO_ENTREGA"],
            "en": bool(d["ENTREGUE"]), "ap": bool(d["APTO"]), "sa": d["SITUACAO_AUT"], "pr": d["PRAZO_AUT"],
            "du": d["DIAS_ATRASO"], "sl": d["SITUACAO_LMR"], "de": d["DIAS_DESDE_EMAIL"], "dt": d["DT_EMAIL"],
            "v": round(float(valor.get((d["LISTA"], d["PMIB"]), 0.0)), 2), "pe": d["PENDENCIA"],
            "pc": pc if isinstance(pc, str) and pc.strip() else proc_lista.get(d["LISTA"]),
        })
    # flags das seções, na ordem de SECOES (itertuples renomeia colunas com espaço; lê direto do DataFrame)
    for reg, (_, linha) in zip(registros, f.iterrows()):
        reg["ok"] = "".join("1" if linha[f"OK_{s}"] else "0" for s in SECOES)

    # ---------------- listas ----------------
    sistemas = f.drop_duplicates("LISTA").set_index("LISTA")[["AREA", "SISTEMA"]].to_dict("index")
    sistemas.update({lst: v for lst, v in itens.drop_duplicates("LISTA").set_index("LISTA")[["AREA", "SISTEMA"]]
                     .to_dict("index").items() if lst not in sistemas})
    listas = []
    vistos = set()
    for _, m in listas_m.iterrows():
        lst = str(m["N DOCUMENTO ITAIPU"]).strip()
        vistos.add(lst)
        s = sistemas.get(lst, {})
        listas.append({"l": lst,
                       "nome": nome_exibicao(s["SISTEMA"]) if s.get("SISTEMA") else nome_curto(m.get("DESCRICAO"), lst),
                       "area": sem_prefixo(s["AREA"]) if s.get("AREA") else None,
                       "et": m.get("ESPECIFICACAO TECNICA"), "cap": m.get("CAPITULO"), "sr": m.get("STATUS REAL"),
                       # [2026-10-26] lista aprovada = família de aprovação do STATUS REAL
                       # (Aprovado, Aprovado com Comentários, Para Assinatura e o antigo APROVADO)
                       "aprov": status_real.eh_aprovacao(m.get("STATUS REAL")),
                       "rev": str(m.get("ULTIMA REVISAO EMITIDA")),
                       "resp": m.get("RESPONSAVEL") if isinstance(m.get("RESPONSAVEL"), str) else None,
                       "proc": m.get("PROCUREMENT") if isinstance(m.get("PROCUREMENT"), str) else None,
                       "ev": m.get("EVENTOS DE PAGAMENTOS RELACIONADOS"), "sit": m.get("SITUACAO NO PMIB")})
    for lst, s in sistemas.items():
        if lst not in vistos:
            listas.append({"l": lst, "nome": nome_exibicao(s["SISTEMA"]), "area": sem_prefixo(s["AREA"]), "sr": None,
                           "rev": None, "resp": None, "proc": None, "ev": None, "sit": "SÓ _STATUS_PMIB"})
    contagem = collections.Counter(x["nome"] for x in listas)
    for x in listas:   # nomes repetidos (ex.: 50 Hz e 60 Hz na mesma pasta) ganham o prefixo RDS-PP
        if contagem[x["nome"]] > 1:
            x["nome"] = f"{x['nome']} · {x['l'][1:5]}"
    for x in listas:
        for k, v in list(x.items()):
            if isinstance(v, float) and pd.isna(v):
                x[k] = None

    # ---------------- listas de preços ----------------
    fu = mapa["precos_followup"]
    precos_out = []
    codigos_fu = set()
    for _, p in fu.iterrows():
        lp = str(p["N DOCUMENTO ITAIPU"]).strip()
        codigos_fu.add(lp)
        st = str(p.get("STATUS DA REVISAO") or "")
        precos_out.append({"lp": lp, "geracao": "PB021" if "PB021" in lp else "PB020-0x",
                           "rev": str(p.get("ULTIMA REVISAO EMITIDA") or ""),
                           "status": st, "data": iso(p.get("DATA DE ATUALIZACAO")),
                           "lista": str(p.get("LISTA DE SOBRESSALENTES") or "").strip() or None,
                           "situacao": "APROVADA SM.DT" if normalizar(st).startswith("APROVADO") else
                                       "CANCELADA" if normalizar(st) == "VOID" else
                                       "NÃO APROVADA" if normalizar(st) == "NAO APROVADO" else "EMITIDA"})
    for _, a in arquivos_preco.iterrows():
        cod = a["ARQUIVO_PRECO"]
        if a["GERACAO"] == "PB021" and cod not in codigos_fu:
            precos_out.append({"lp": cod, "geracao": "PB021", "rev": "", "status": "arquivo na pasta — falta no follow-up",
                               "data": a["MODIFICADO"], "lista": cod.replace("PB021", "PB020"), "situacao": "EMITIDA"})

    # ---------------- atividades ----------------
    atv = []
    for _, a in mapa["atividades"].iterrows():
        status = normalizar(a.get("STATUS"))
        fim_prev = iso(a.get("PREVISAO DE TERMINO"))
        concl = a.get("CONCLUIDA") is True or status == "CONCLUIDA"
        sit = ("CONCLUÍDA" if concl else "TRAVADA" if status == "TRAVADA" else
               "ATRASADA" if fim_prev and fim_prev < hoje.isoformat() else
               "NÃO INICIADA" if not iso(a.get("DATA DE INICIO")) else "EM DIA")
        atv.append({"lista": a.get("LISTA"), "frente": a.get("GRUPO"), "atividade": a.get("DESCRICAO"), "sit": sit,
                    "fim_prev": fim_prev, "quem": a.get("COM QUEM ESTA") if isinstance(a.get("COM QUEM ESTA"), str) else None})

    _log(" -> Painel: conferindo a qualidade dos dados...")
    return {"ref": hoje.isoformat(), "gerado": dt.date.today().isoformat(), "itens": registros, "listas": listas,
            "precos": precos_out, "atividades": atv, "qualidade": qualidade(itens, precos, mapa, f, raiz)}


# --------------------------------------------------------------------------
# Qualidade dos dados -- cada achado diz onde corrigir
# --------------------------------------------------------------------------
def qualidade(itens: pd.DataFrame, precos: pd.DataFrame, mapa: dict, fichas: pd.DataFrame,
              raiz: pathlib.Path) -> list[dict]:
    q = []

    bruto = itens["CODIGO PMIB"].astype(str).str.strip()
    torto = itens[itens["PMIB"].notna() & (bruto != itens["PMIB"])]
    if len(torto):
        q.append({"titulo": "códigos PMIB fora do formato", "n": len(torto),
                  "detalhe": "Gravados sem o ponto ou como número (perdem o zero). O painel corrige na leitura; o certo é texto 4500063671.0000.",
                  "exemplos": sorted(set(bruto[torto.index]))[:4]})

    sem = fichas[fichas["STATUS_N"].isin(["N/A", "SEM STATUS"])]
    if len(sem):
        c = collections.Counter(sem["LISTA"])
        q.append({"titulo": "fichas com STATUS N/A ou vazio", "n": len(sem),
                  "detalhe": "Têm código PMIB, então são fichas: N/A só vale para linha sem ficha (título de conjunto). "
                             "Provável FICHA CRIADA — corrigir no _STATUS_PMIB.",
                  "exemplos": [f"{lst} ({n})" for lst, n in c.most_common(4)]})

    dup = itens[itens["STATUS_N"] == "DUPLICADO"]
    fichas_lista = set(zip(itens.loc[itens["E_FICHA"], "LISTA"], itens.loc[itens["E_FICHA"], "PMIB"]))
    orfas = dup[[(lst, p) not in fichas_lista for lst, p in zip(dup["LISTA"], dup["PMIB"])]]
    if len(orfas):
        q.append({"titulo": "linhas DUPLICADO sem a linha original na mesma lista", "n": len(orfas),
                  "detalhe": "DUPLICADO = o mesmo item repetido na mesma lista; a linha tem de repetir o PMIB de outra linha "
                             "da lista. Sem PMIB ou sem a original, a ficha some da contagem.",
                  "exemplos": [f"{lst} · item {i} · {p or 'sem PMIB'}"
                               for lst, i, p in zip(orfas["LISTA"], orfas["ITEM"], orfas["PMIB"])][:4]})

    sem_ref = itens[itens["DUP_OUTRO_SISTEMA"] & itens["PMIB_ORIGINAL"].isna() & itens["E_FICHA"]]
    if len(sem_ref):
        q.append({"titulo": "fichas duplicadas de outro sistema sem o PMIB da original", "n": len(sem_ref),
                  "detalhe": "PDM.9900.000 exige o PMIB da ficha original em OBSERVAÇÕES — é de onde o módulo Ficha Duplicada copia.",
                  "exemplos": [f"{lst} · {p}" for lst, p in zip(sem_ref["LISTA"], sem_ref["PMIB"])][:4]})

    apto_sem = fichas[fichas["APTO"] & fichas["DT_EMAIL"].isna()]
    if len(apto_sem):
        q.append({"titulo": "fichas APTAS sem data do e-mail de intenção", "n": len(apto_sem),
                  "detalhe": "Sem a data, não dá para medir prazo de Itaipu nem o compromisso de LMR. Histórico anterior ao controle de datas.",
                  "exemplos": [f"{lst} ({n})" for lst, n in collections.Counter(apto_sem["LISTA"]).most_common(4)]})

    val = itens["VALORIZACAO"].map(lambda v: isinstance(v, (int, float)) and not pd.isna(v))
    if val.sum():
        q.append({"titulo": "células de VALORIZAÇÃO com número", "n": int(val.sum()),
                  "detalhe": "A coluna é de estado (COMPLETO / INCOMPLETO / N/A). Preço vai na lista de preços; o número quebra a contagem.",
                  "exemplos": [f"{lst} ({n})" for lst, n in collections.Counter(itens.loc[val, "LISTA"]).most_common(4)]})

    nc = fichas[fichas["TIPO_ENTREGA"] == "NÃO CLASSIFICADO"]
    if len(nc):
        q.append({"titulo": "fichas sem tipo de entrega", "n": len(nc),
                  "detalhe": "Sem lista de preços com a coluna TIPO DE ENTREGA. Preencher no _STATUS_PMIB v2 — sem isso não dá para separar o que vai na nota fiscal.",
                  "exemplos": [f"{lst} ({n})" for lst, n in collections.Counter(nc["LISTA"]).most_common(4)]})

    if len(precos):
        fis_sem_ge = precos[(precos["TIPO"] == "FÍSICA E DOCUMENTAL")
                            & precos["CODIGO_GE"].map(lambda v: normalizar(v) in ("", "-"))]
        if len(fis_sem_ge):
            q.append({"titulo": "itens físicos sem código GE na lista de preços", "n": len(fis_sem_ge),
                      "detalhe": "Item que sai na nota fiscal precisa do código GE (MTA). Regra: código GE preenchido ⟺ FÍSICA E DOCUMENTAL.",
                      "exemplos": sorted(set(fis_sem_ge["ARQUIVO_PRECO"]))[:4]})

    fu = mapa["precos_followup"]
    antigos = [c for c in fu["N DOCUMENTO ITAIPU"].astype(str) if "PB021" not in c] if len(fu) else []
    if antigos:
        q.append({"titulo": "listas de preços no follow-up com código antigo (PB020-0x)", "n": len(antigos),
                  "detalhe": "Pela revisão do ITAIPU-REF-0013 a lista de preços é PB021. A aba 'Lista de preços Follow-up' ainda não tem nenhuma PB021.",
                  "exemplos": antigos[:4]})

    copias = [p.name for p in raiz.rglob("*") if p.is_file() and p.suffix.lower() in (".xlsx", ".xlsm")
              and "00 - OBSOLETO" not in str(p)
              and re.search(r"STATUS_PMIB_\.xlsx$| - Copy|corrigido|testes_autospec", str(p), re.I)]
    if copias:
        q.append({"titulo": "cópias de trabalho misturadas às planilhas vivas", "n": len(copias),
                  "detalhe": "Quem varre a árvore (SIG-FT, Power BI) pode contar em dobro. Mover para uma subpasta _obsoleto.",
                  "exemplos": copias[:4]})

    sem_resp = mapa["listas"]["RESPONSAVEL"].map(lambda v: normalizar(v) in ("", "-", "NAN")).sum()
    if sem_resp:
        q.append({"titulo": "listas sem responsável na mapeadora", "n": int(sem_resp),
                  "detalhe": "Lista sem dono é lista que ninguém está puxando.", "exemplos": []})

    ext = 0
    for p in arquivos_status_pmib(raiz):
        with zipfile.ZipFile(p) as z:
            ext += any("<x14:dataValidation " in z.read(n).decode("utf-8", "ignore")
                       for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
    if ext:
        # O título e o detalhe são os do painel de referência (o validador os
        # compara). Desde a T1 o SIG-FT não apaga mais essas listas -- ver
        # PENDENCIAS: reescrever vale para os dois painéis.
        q.append({"titulo": "planilhas com lista suspensa que some ao salvar pelo SIG-FT", "n": ext,
                  "detalhe": "A validação aponta para outra aba (Checklist!$A$3:$A$8) e é gravada como extensão, que o openpyxl apaga. "
                             "A migração v2 recria por nome definido.", "exemplos": []})

    return q


# --------------------------------------------------------------------------
# A página
# --------------------------------------------------------------------------
def limpar(v):
    """NaN/NaT viram null -- JSON não tem NaN, e o navegador recusa o arquivo inteiro."""
    if isinstance(v, dict):
        return {k: limpar(x) for k, x in v.items()}
    if isinstance(v, list):
        return [limpar(x) for x in v]
    if v is pd.NaT or (isinstance(v, float) and pd.isna(v)):
        return None
    if hasattr(v, "item") and not isinstance(v, str):   # numpy -> python
        return limpar(v.item())
    return v


def caminho_do_template() -> pathlib.Path:
    """O template da página: ao lado do pacote (`sigft/assets/`), inclusive
    dentro do .exe (o `SIG-FT.spec` o leva para lá)."""
    candidatos = [pathlib.Path(__file__).resolve().parents[1] / "assets" / NOME_DO_TEMPLATE]
    base_do_pacote = getattr(sys, "_MEIPASS", None)
    if base_do_pacote:
        candidatos.insert(0, pathlib.Path(base_do_pacote) / "sigft" / "assets" / NOME_DO_TEMPLATE)
    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    raise FileNotFoundError(f"template do painel não encontrado: {candidatos[-1]}")


def gerar_html(dados: dict) -> str:
    """Os dados vão inteiros dentro da página (`<script id="dados">`): o HTML
    abre sem rede e sem servidor. `</` vira `<\\/` para nenhum texto de célula
    fechar o `<script>` antes da hora."""
    texto = json.dumps(dados, ensure_ascii=False, default=str, allow_nan=False).replace("</", "<\\/")
    return caminho_do_template().read_text(encoding="utf-8").replace("/*__DADOS__*/", texto)


def gerar_painel(pasta_pmib, mapeadora, saida, hoje: dt.date | None = None, callback_log=None) -> pathlib.Path:
    """Gera o painel e grava em `saida` (sobrescreve: o Box guarda as versões).
    Devolve o caminho gravado.

    Levanta o erro de leitura ou de gravação (ex.: `PermissionError` com o
    arquivo bloqueado) para quem chama decidir -- no Gestão PMIB, falhar o
    painel nunca desfaz a gravação dos `_STATUS_PMIB`."""
    hoje = hoje or dt.date.today()
    dados = limpar(montar(hoje, pasta_pmib, mapeadora, callback_log=callback_log))
    saida = pathlib.Path(saida)
    saida.write_text(gerar_html(dados), encoding="utf-8")
    if callback_log:
        callback_log(f" -> Painel gravado: {os.path.basename(str(saida))} ({len(dados['itens'])} fichas, "
                     f"{len(dados['listas'])} listas, {len(dados['qualidade'])} achado(s) de qualidade).")
    return saida
