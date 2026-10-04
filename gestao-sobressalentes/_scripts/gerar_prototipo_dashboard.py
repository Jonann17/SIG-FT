# -*- coding: utf-8 -*-
"""
Gera o prototipo do painel de sobressalentes (visao interna + visao Itaipu)
a partir dos _STATUS_PMIB, das listas de precos e da mapeadora.

REGRA INEGOCIAVEL: este script **so le** o Box. Escreve apenas
`_gerado/prototipo-dashboard.html`, dentro do cofre.

O prototipo e o desenho-alvo do Power BI (`_gestao_v2/powerbi/`): mesmas
regras (`regras_sobressalentes.py`), mesmos numeros.

Uso:
    python _scripts/gerar_prototipo_dashboard.py

Requisitos: openpyxl, pandas
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import re
import sys
import zipfile

import pandas as pd

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import regras_sobressalentes as R  # noqa: E402

VAULT = AQUI.parent
SAIDA = VAULT / "_gerado" / "prototipo-dashboard.html"
MODELO = AQUI / "prototipo_template.html"


def iso(v) -> str | None:
    if isinstance(v, (dt.datetime, pd.Timestamp)):
        return None if pd.isna(v) else v.date().isoformat()
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
    """Nome curto para grafico: a ultima pasta, com a de cima quando a ultima sozinha nao diz nada."""
    partes = []
    for p in sistema.split(" › "):
        if re.fullmatch(r"R\d+[A-Z]?", p):          # pasta de revisao (R0A) nao e nome
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


def montar(hoje: dt.date) -> dict:
    precos, arquivos_preco = R.ler_listas_precos()
    itens = R.ler_itens(hoje=hoje, precos=precos)
    mapa = R.ler_mapeadora()
    listas_m = mapa["listas"]

    # procurement por lista (mapeadora), usado enquanto a coluna do _STATUS_PMIB v2 estiver vazia
    proc_lista = {str(l).strip(): (p if isinstance(p, str) else None) for l, p in zip(listas_m["N DOCUMENTO ITAIPU"], listas_m["PROCUREMENT"])}

    # ---------------- fichas (lista|PMIB) ----------------
    # valor: TODAS as linhas da ficha, inclusive as DUPLICADO (repeticao na mesma lista tem quantidade propria)
    com_pmib = itens[itens["PMIB"].notna()].copy()
    com_pmib["VALOR_LINHA"] = [q * v if (t == "FÍSICA E DOCUMENTAL" and pd.notna(q) and v is not None and pd.notna(v)) else 0.0
                               for q, v, t in zip(com_pmib["QTD"], com_pmib["VALOR_UNIT"], com_pmib["TIPO_ENTREGA"])]
    valor = com_pmib.groupby(["LISTA", "PMIB"])["VALOR_LINHA"].sum()
    # estado: a linha da ficha (a que nao e DUPLICADO)
    f = itens[itens["E_FICHA"]].copy().drop_duplicates(["LISTA", "PMIB"])
    registros = []
    for r in f.itertuples(index=False):
        d = r._asdict()
        pc = d.get("PROCUREMENT")
        registros.append({
            "l": d["LISTA"], "a": sem_prefixo(d["AREA"]), "s": nome_exibicao(d["SISTEMA"]), "p": d["PMIB"],
            "d": str(d["DESCRICAO"])[:90], "st": d["STATUS_N"], "q": d["COM_QUEM"], "t": d["TIPO_ENTREGA"],
            "en": bool(d["ENTREGUE"]), "ap": bool(d["APTO"]), "sa": d["SITUACAO_AUT"], "pr": d["PRAZO_AUT"],
            "du": d["DU_ATRASO"], "sl": d["SITUACAO_LMR"], "de": d["DIAS_DESDE_EMAIL"], "dt": d["DT_EMAIL"],
            "v": round(float(valor.get((d["LISTA"], d["PMIB"]), 0.0)), 2), "pe": d["PENDENCIA"],
            "pc": pc if isinstance(pc, str) and pc.strip() else proc_lista.get(d["LISTA"]),
        })
    # flags das secoes, na ordem de R.SECOES (itertuples renomeia colunas com espaco; le direto do DataFrame)
    for reg, (_, linha) in zip(registros, f.iterrows()):
        reg["ok"] = "".join("1" if linha[f"OK_{s}"] else "0" for s in R.SECOES)

    # ---------------- listas ----------------
    sistemas = f.drop_duplicates("LISTA").set_index("LISTA")[["AREA", "SISTEMA"]].to_dict("index")
    sistemas.update({l: v for l, v in itens.drop_duplicates("LISTA").set_index("LISTA")[["AREA", "SISTEMA"]].to_dict("index").items()
                     if l not in sistemas})
    listas = []
    vistos = set()
    for _, m in listas_m.iterrows():
        l = str(m["N DOCUMENTO ITAIPU"]).strip()
        vistos.add(l)
        s = sistemas.get(l, {})
        listas.append({"l": l, "nome": nome_exibicao(s["SISTEMA"]) if s.get("SISTEMA") else nome_curto(m.get("DESCRICAO"), l),
                       "area": sem_prefixo(s["AREA"]) if s.get("AREA") else None,
                       "et": m.get("ESPECIFICACAO TECNICA"), "sr": m.get("STATUS REAL"), "rev": str(m.get("ULTIMA REVISAO EMITIDA")),
                       "resp": m.get("RESPONSAVEL") if isinstance(m.get("RESPONSAVEL"), str) else None,
                       "proc": m.get("PROCUREMENT") if isinstance(m.get("PROCUREMENT"), str) else None,
                       "ev": m.get("EVENTOS DE PAGAMENTOS RELACIONADOS"), "sit": m.get("SITUACAO NO PMIB")})
    for l, s in sistemas.items():
        if l not in vistos:
            listas.append({"l": l, "nome": nome_exibicao(s["SISTEMA"]), "area": sem_prefixo(s["AREA"]), "sr": None, "rev": None, "resp": None,
                           "proc": None, "ev": None, "sit": "SÓ _STATUS_PMIB"})
    contagem = collections.Counter(x["nome"] for x in listas)
    for x in listas:   # nomes repetidos (ex.: 50 Hz e 60 Hz na mesma pasta) ganham o prefixo RDS-PP
        if contagem[x["nome"]] > 1:
            x["nome"] = f"{x['nome']} · {x['l'][1:5]}"
    for x in listas:
        for k, v in list(x.items()):
            if isinstance(v, float) and pd.isna(v):
                x[k] = None

    # ---------------- listas de precos ----------------
    fu = mapa["precos_followup"]
    precos_out = []
    codigos_fu = set()
    for _, p in fu.iterrows():
        lp = str(p["N DOCUMENTO ITAIPU"]).strip()
        codigos_fu.add(lp)
        st = str(p.get("STATUS DA REVISAO") or "")
        precos_out.append({"lp": lp, "geracao": "PB021" if "PB021" in lp else "PB020-0x", "rev": str(p.get("ULTIMA REVISAO EMITIDA") or ""),
                           "status": st, "data": iso(p.get("DATA DE ATUALIZACAO")),
                           "lista": str(p.get("LISTA DE SOBRESSALENTES") or "").strip() or None,
                           "situacao": "APROVADA SM.DT" if R.normalizar(st).startswith("APROVADO") else
                                       "CANCELADA" if R.normalizar(st) == "VOID" else
                                       "NÃO APROVADA" if R.normalizar(st) == "NAO APROVADO" else "EMITIDA"})
    for _, a in arquivos_preco.iterrows():
        cod = a["ARQUIVO_PRECO"]
        if a["GERACAO"] == "PB021" and cod not in codigos_fu:
            precos_out.append({"lp": cod, "geracao": "PB021", "rev": "", "status": "arquivo na pasta — falta no follow-up",
                               "data": a["MODIFICADO"], "lista": cod.replace("PB021", "PB020"), "situacao": "EMITIDA"})

    # ---------------- atividades ----------------
    atv = []
    for _, a in mapa["atividades"].iterrows():
        status = R.normalizar(a.get("STATUS"))
        fim_prev = iso(a.get("PREVISAO DE TERMINO"))
        concl = a.get("CONCLUIDA") is True or status == "CONCLUIDA"
        sit = ("CONCLUÍDA" if concl else "TRAVADA" if status == "TRAVADA" else
               "ATRASADA" if fim_prev and fim_prev < hoje.isoformat() else
               "NÃO INICIADA" if not iso(a.get("DATA DE INICIO")) else "EM DIA")
        atv.append({"lista": a.get("LISTA"), "frente": a.get("GRUPO"), "atividade": a.get("DESCRICAO"), "sit": sit,
                    "fim_prev": fim_prev, "quem": a.get("COM QUEM ESTA") if isinstance(a.get("COM QUEM ESTA"), str) else None})

    return {"ref": hoje.isoformat(), "gerado": dt.date.today().isoformat(), "itens": registros, "listas": listas,
            "precos": precos_out, "atividades": atv, "qualidade": qualidade(itens, precos, arquivos_preco, mapa, f)}


# --------------------------------------------------------------------------
# Qualidade dos dados — cada achado diz onde corrigir
# --------------------------------------------------------------------------
def qualidade(itens: pd.DataFrame, precos: pd.DataFrame, arquivos_preco: pd.DataFrame, mapa: dict, fichas: pd.DataFrame) -> list[dict]:
    q = []
    nome = lambda l: l  # noqa: E731

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
                  "exemplos": [f"{l} ({n})" for l, n in c.most_common(4)]})

    dup = itens[itens["STATUS_N"] == "DUPLICADO"]
    fichas_lista = set(zip(itens.loc[itens["E_FICHA"], "LISTA"], itens.loc[itens["E_FICHA"], "PMIB"]))
    orfas = dup[[(l, p) not in fichas_lista for l, p in zip(dup["LISTA"], dup["PMIB"])]]
    if len(orfas):
        q.append({"titulo": "linhas DUPLICADO sem a linha original na mesma lista", "n": len(orfas),
                  "detalhe": "DUPLICADO = o mesmo item repetido na mesma lista; a linha tem de repetir o PMIB de outra linha "
                             "da lista. Sem PMIB ou sem a original, a ficha some da contagem.",
                  "exemplos": [f"{l} · item {i} · {p or 'sem PMIB'}" for l, i, p in zip(orfas["LISTA"], orfas["ITEM"], orfas["PMIB"])][:4]})

    sem_ref = itens[itens["DUP_OUTRO_SISTEMA"] & itens["PMIB_ORIGINAL"].isna() & itens["E_FICHA"]]
    if len(sem_ref):
        q.append({"titulo": "fichas duplicadas de outro sistema sem o PMIB da original", "n": len(sem_ref),
                  "detalhe": "PDM.9900.000 exige o PMIB da ficha original em OBSERVAÇÕES — é de onde o módulo Ficha Duplicada copia.",
                  "exemplos": [f"{l} · {p}" for l, p in zip(sem_ref["LISTA"], sem_ref["PMIB"])][:4]})

    apto_sem = fichas[fichas["APTO"] & fichas["DT_EMAIL"].isna()]
    if len(apto_sem):
        q.append({"titulo": "fichas APTAS sem data do e-mail de intenção", "n": len(apto_sem),
                  "detalhe": "Sem a data, não dá para medir prazo de Itaipu nem o compromisso de LMR. Histórico anterior ao controle de datas.",
                  "exemplos": [f"{l} ({n})" for l, n in collections.Counter(apto_sem["LISTA"]).most_common(4)]})

    val = itens["VALORIZACAO"].map(lambda v: isinstance(v, (int, float)) and not pd.isna(v))
    if val.sum():
        q.append({"titulo": "células de VALORIZAÇÃO com número", "n": int(val.sum()),
                  "detalhe": "A coluna é de estado (COMPLETO / INCOMPLETO / N/A). Preço vai na lista de preços; o número quebra a contagem.",
                  "exemplos": [f"{l} ({n})" for l, n in collections.Counter(itens.loc[val, "LISTA"]).most_common(4)]})

    nc = fichas[fichas["TIPO_ENTREGA"] == "NÃO CLASSIFICADO"]
    if len(nc):
        q.append({"titulo": "fichas sem tipo de entrega", "n": len(nc),
                  "detalhe": "Sem lista de preços com a coluna TIPO DE ENTREGA. Preencher no _STATUS_PMIB v2 — sem isso não dá para separar o que vai na nota fiscal.",
                  "exemplos": [f"{l} ({n})" for l, n in collections.Counter(nc["LISTA"]).most_common(4)]})

    if len(precos):
        fis_sem_ge = precos[(precos["TIPO"] == "FÍSICA E DOCUMENTAL") & precos["CODIGO_GE"].map(lambda v: R.normalizar(v) in ("", "-"))]
        if len(fis_sem_ge):
            q.append({"titulo": "itens físicos sem código GE na lista de preços", "n": len(fis_sem_ge),
                      "detalhe": "Item que sai na nota fiscal precisa do código GE (MTA). Regra: código GE preenchido ⟺ FÍSICA E DOCUMENTAL.",
                      "exemplos": sorted(set(fis_sem_ge["ARQUIVO_PRECO"]))[:4]})

    fu = mapa["precos_followup"]
    antigos = [c for c in fu["N DOCUMENTO ITAIPU"].astype(str) if "PB021" not in c]
    if antigos:
        q.append({"titulo": "listas de preços no follow-up com código antigo (PB020-0x)", "n": len(antigos),
                  "detalhe": "Pela revisão do ITAIPU-REF-0013 a lista de preços é PB021. A aba 'Lista de preços Follow-up' ainda não tem nenhuma PB021.",
                  "exemplos": antigos[:4]})

    lm = mapa["listas"].set_index(mapa["listas"]["N DOCUMENTO ITAIPU"].astype(str).str.strip())
    contagem = fichas.groupby("LISTA")["PMIB"].nunique()
    difs = [(l, int(lm.at[l, "FICHAS EXISTENTES"] or 0), int(n)) for l, n in contagem.items()
            if l in lm.index and pd.notna(lm.at[l, "FICHAS EXISTENTES"]) and int(lm.at[l, "FICHAS EXISTENTES"]) != int(n)]
    if difs:
        q.append({"titulo": "listas com FICHAS EXISTENTES diferente do _STATUS_PMIB", "n": len(difs),
                  "detalhe": "A mapeadora só acerta depois de o SIG-FT rodar. Por isso o painel conta direto da ficha.",
                  "exemplos": [f"{l}: mapeadora {a} × arquivo {b}" for l, a, b in difs[:3]]})

    copias = [p.name for p in R.PASTA_PMIB.rglob("*") if p.is_file() and p.suffix.lower() in (".xlsx", ".xlsm")
              and "00 - OBSOLETO" not in str(p) and re.search(r"STATUS_PMIB_\.xlsx$| - Copy|corrigido|testes_autospec", str(p), re.I)]
    if copias:
        q.append({"titulo": "cópias de trabalho misturadas às planilhas vivas", "n": len(copias),
                  "detalhe": "Quem varre a árvore (SIG-FT, Power BI) pode contar em dobro. Mover para uma subpasta _obsoleto.",
                  "exemplos": copias[:4]})

    sem_resp = mapa["listas"]["RESPONSAVEL"].map(lambda v: R.normalizar(v) in ("", "-", "NAN")).sum()
    if sem_resp:
        q.append({"titulo": "listas sem responsável na mapeadora", "n": int(sem_resp),
                  "detalhe": "Lista sem dono é lista que ninguém está puxando.", "exemplos": []})

    ext = 0
    for p in R.listar_status_pmib():
        with zipfile.ZipFile(p) as z:
            ext += any("<x14:dataValidation " in z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
    if ext:
        q.append({"titulo": "planilhas com lista suspensa que some ao salvar pelo SIG-FT", "n": ext,
                  "detalhe": "A validação aponta para outra aba (Checklist!$A$3:$A$8) e é gravada como extensão, que o openpyxl apaga. "
                             "A migração v2 recria por nome definido.", "exemplos": []})

    soma_map = pd.to_numeric(mapa["listas"]["ATRASO DE AUTORIZACAO DE ENTREGA ITAIPU"], errors="coerce").sum()
    novo = int((fichas["SITUACAO_AUT"] == "ATRASADO ITAIPU").sum())
    q.append({"titulo": "atraso de autorização: regra antiga ainda no SIG-FT", "n": novo,
              "detalhe": f"Fichas atrasadas pela regra de 15 dias úteis. A mapeadora mostra {int(soma_map)}, calculado pelo SIG-FT com 14 dias corridos "
                         "(sigft/services/pmib_manager.py, pd.to_timedelta(14, unit='D')).", "exemplos": []})
    return q


def limpar(v):
    """NaN/NaT viram null — JSON nao tem NaN e o navegador recusa o arquivo inteiro."""
    if isinstance(v, dict):
        return {k: limpar(x) for k, x in v.items()}
    if isinstance(v, list):
        return [limpar(x) for x in v]
    if v is pd.NaT or (isinstance(v, float) and pd.isna(v)):
        return None
    if hasattr(v, "item") and not isinstance(v, str):   # numpy -> python
        return limpar(v.item())
    return v


def main() -> int:
    if not R.MAPEADORA.exists():
        sys.exit(f"Mapeadora nao encontrada:\n  {R.MAPEADORA}\nO Box esta sincronizado?")
    dados = limpar(montar(dt.date.today()))
    texto = json.dumps(dados, ensure_ascii=False, default=str, allow_nan=False).replace("</", "<\\/")
    html = MODELO.read_text(encoding="utf-8").replace("/*__DADOS__*/", texto)
    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(html, encoding="utf-8")
    print(f"OK: {SAIDA}  ({len(dados['itens'])} fichas, {len(dados['listas'])} listas, {len(dados['qualidade'])} achados de qualidade)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
