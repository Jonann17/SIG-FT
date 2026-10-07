# -*- coding: utf-8 -*-
"""
Kit de teste da T6 do SIG-FT: gerar a LISTA DE PRECOS revisao 0A a partir do _STATUS_PMIB.

Saida em _gestao_v2/fixtures/kit_lista_precos/:
  Lista de Sobressalentes com preço.xlsm      copia do template oficial (Box/15 - PDM/Templates)
  status/#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx _STATUS_PMIB v2 sintetico com TIPO em todas as linhas
                                                (o do kit_gestao_pmib, que tem TIPO vazio, serve de caso de RECUSA)
  esperado_lista_precos.json                   parametros da tela + o resultado certo, celula a celula

O esperado segue as regras da secao T6 do roteiro (07 - Diagnostico/Tarefa SIG-FT ...). Nao ha
gerador de referencia aqui (decisao do Luan, 05/10/2026: a validacao final e com listas reais).

Uso:  python _gestao_v2/gerar_kit_lista_precos.py
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys
import warnings

import openpyxl

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "_scripts"))
sys.path.insert(0, str(AQUI))
import regras_sobressalentes as R  # noqa: E402
from xlsx_cirurgico import PlanilhaXlsx  # noqa: E402
from migrar_status_pmib_v2 import cabecalho  # noqa: E402

KIT = AQUI / "fixtures" / "kit_lista_precos"
TEMPLATE = R.PASTA_PMIB.parent / "Templates" / "Lista de Sobressalentes com preço.xlsm"
ORIGEM = AQUI / "fixtures" / "kit_gestao_pmib" / "status" / "#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx"
F, D, T = "FÍSICA E DOCUMENTAL", "DOCUMENTAL", "TÍTULO"
# TIPO por linha do _STATUS_PMIB sintetico (6..22); linha 10 = DOCUMENTAL COM codigo CMI (deve gerar AVISO)
TIPOS = {6: F, 7: F, 8: F, 9: F, 10: D, 11: T, 12: F, 13: F, 14: F, 15: D, 16: F, 17: F, 18: D,
         19: F, 20: F, 21: F, 22: F}
DOCUMENTAL_SEM_CMI = {15, 18}           # componente explodido de verdade: sem codigo CMI/GE

PARAMETROS = {                          # o que a tela do SIG-FT pede (pre-preenchido) — valores de teste
    "codigo_itaipu": "#ST00=TESTE01&MPB021",
    "controle_emitente": "TESTE-CMI-PRECO-01",
    "disciplina": "ENG. ELÉTRICA",
    "sistema": "TEXTO DE TESTE SISTEMA",
    "titulo": "TEXTO DE TESTE EQUIPAMENTO",
    "autoria": "FULANO DE TAL; BELTRANO SILVA",
    "verificacao": "CICRANO SOUZA",
    "aprovacao": "MARIA PEREIRA",
    "data": "2026-10-10",
    "incluir_duplicados": True,
}


def montar_status(destino: pathlib.Path) -> None:
    shutil.copy2(ORIGEM, destino)
    p = PlanilhaXlsx(destino)
    L = p.parte_da_aba("Lista de Materiais")
    for r, tipo in TIPOS.items():
        p.escrever(L, f"Q{r}", tipo)
        p.escrever(L, f"F{r}", None if r in DOCUMENTAL_SEM_CMI else f"TESTE-CMI-{r:03d}")   # CÓDIGO CMI
    p.escrever(L, "X6", "NOTA INTERNA — NÃO PODE IR PARA A LISTA DE PREÇOS")     # OBSERVAÇÕES
    p.escrever(L, "H7", " 4500063671.9006 ")                                      # PMIB com espaços
    p.salvar()


PARTICULAS = {"DE", "DA", "DO", "DAS", "DOS", "E"}


def iniciais(nome: str) -> str:
    """'LUAN COZER' -> 'LC'; 'FULANO DE TAL' -> 'FT' (sem partículas)."""
    return "".join(p[0] for p in nome.upper().split() if p[:1].isalpha() and p not in PARTICULAS)


def esperado(status: pathlib.Path) -> dict:
    ws = openpyxl.load_workbook(status)["Lista de Materiais"]
    hdr, mapa = cabecalho(ws)
    c = lambda n: mapa[R.normalizar(n)]  # noqa: E731
    linhas, avisos, r_saida = {}, [], 5
    for r in range(hdr + 1, ws.max_row + 1):
        if R.normalizar(ws.cell(r, c("DESCRIÇÃO")).value) == "":
            continue
        if R.normalizar(ws.cell(r, c("STATUS")).value) == "DUPLICADO" and not PARAMETROS["incluir_duplicados"]:
            continue
        tipo = R.TIPO_CANONICO.get(R.normalizar(ws.cell(r, c("TIPO DE ENTREGA")).value))
        cmi = ws.cell(r, c("CÓDIGO CMI")).value
        pmib_bruto = ws.cell(r, c("CÓDIGO PMIB")).value
        if tipo == D and cmi not in (None, ""):
            avisos.append(f"linha {r} do _STATUS_PMIB: DOCUMENTAL com CÓDIGO CMI — CÓDIGO GE deixado vazio")
        linhas[str(r_saida)] = {
            "origem": r,
            "A": ws.cell(r, c("ITEM")).value, "B": ws.cell(r, c("QTD.")).value, "C": ws.cell(r, c("UNID.")).value,
            "D": ws.cell(r, c("DESCRIÇÃO")).value, "E": ws.cell(r, c("MARCA/MODELO")).value,
            "F": ws.cell(r, c("CÓDIGO DO MATERIAL")).value,
            "G": None if tipo == D else cmi,
            "H": R.normalizar_pmib(pmib_bruto) or (str(pmib_bruto).strip() if pmib_bruto not in (None, "") else None),
            "I": None,
            "J": tipo,
        }
        r_saida += 1
    ultima = r_saida - 1
    codigo_rodape = PARAMETROS["codigo_itaipu"].replace("&", "&&")
    return {
        "parametros": PARAMETROS,
        "saida_nome": PARAMETROS["codigo_itaipu"] + ".xlsm",
        "lista_de_materiais": {
            "linhas": linhas,
            "linhas_limpas": {"de": ultima + 1, "ate": 41, "colunas": "A..K vazias (numeração e exemplos do template removidos)"},
            "K5_vazia": True,
            "area_de_impressao": f"'Lista de Materiais'!$A$2:$J${max(ultima, 5)}",
            "C2_valor_em_cache": f"{PARAMETROS['titulo']} - LISTA DE SOBRESSALENTE COM PREÇO",
            "nunca_copiar": ["OBSERVAÇÕES", "STATUS", "PDM usado", "seções", "DATA DO EMAIL", "SITUAÇÃO", "DIAS DE ATRASO",
                             "EQUIPAMENTO ENTREGUE", "FORNECEDOR", "PROCUREMENT"],
        },
        "capa": {"E25": PARAMETROS["disciplina"], "E26": PARAMETROS["sistema"],
                 "E27": f"{PARAMETROS['titulo']} - LISTA DE SOBRESSALENTE COM PREÇO",
                 "B31": PARAMETROS["autoria"], "B33": PARAMETROS["verificacao"], "B35": PARAMETROS["aprovacao"],
                 "B37": PARAMETROS["data"], "D37": PARAMETROS["controle_emitente"], "F37": PARAMETROS["codigo_itaipu"],
                 "I37": "0A"},
        "contracapa": {"A12": "0A", "B12": "-", "D12": "PRIMEIRA EMISSÃO",
                       "E12": "; ".join(iniciais(n) for n in PARAMETROS["autoria"].split(";")),
                       "F12": iniciais(PARAMETROS["verificacao"]), "G12": iniciais(PARAMETROS["aprovacao"]),
                       "H12": PARAMETROS["data"]},
        "rodapes": {
            "quem_faz": "a MACRO ConfigurarRodapeCompleto, disparada ao regravar Capa!D37/F37/I37 no Excel (passo 2 da T6) "
                        "— o SIG-FT nunca escreve rodapé",
            "abas": ["Contracapa", "Lista de Materiais"],
            "sem_excel": "rodapé idêntico ao do template (o passo 1 não toca nele)",
            "com_excel_o_que_a_macro_deixa": {"CMI-XXXXXXXX": PARAMETROS["controle_emitente"],
                                              "XXXXXXXXXXXX": codigo_rodape, "Rxx": "0A"},
        },
        "partes_byte_a_byte_iguais_sem_excel": ["xl/vbaProject.bin", "xl/embeddings/Microsoft_Word_97_-_2003_Document.doc",
                                                "xl/worksheets/sheet4.xml", "xl/media/*", "xl/drawings/*"],
        "macro_presente_com_excel": "xl/vbaProject.bin existe e o código tem ConfigurarRodapeCompleto e Worksheet_Change",
        "avisos": avisos,
        "recusas": {
            "kit_gestao_pmib/status/#ST00=TESTE01&MPB020_STATUS_PMIB.xlsx":
                "recusar: fichas sem TIPO DE ENTREGA nas linhas 12, 19, 20, 21, 22 — listar e parar",
            "saida ja existe": "recusar: nunca sobrescrever uma lista de preços",
            "arquivo sem a coluna TIPO DE ENTREGA": "recusar: _STATUS_PMIB fora do layout v2",
        },
    }


def main() -> None:
    if KIT.exists():
        shutil.rmtree(KIT)
    (KIT / "status").mkdir(parents=True)
    shutil.copy2(TEMPLATE, KIT / TEMPLATE.name)
    st = KIT / "status" / ORIGEM.name
    montar_status(st)
    esp = esperado(st)
    (KIT / "esperado_lista_precos.json").write_text(json.dumps(esp, ensure_ascii=False, indent=2, default=str),
                                                    encoding="utf-8")
    print(len(esp["lista_de_materiais"]["linhas"]), "linhas de item;", esp["lista_de_materiais"]["area_de_impressao"])
    for k, v in list(esp["lista_de_materiais"]["linhas"].items())[:4]:
        print(k, {c: v[c] for c in "AGHJ"})
    print("avisos:", esp["avisos"])


if __name__ == "__main__":
    main()
