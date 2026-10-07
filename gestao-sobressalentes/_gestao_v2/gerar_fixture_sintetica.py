# -*- coding: utf-8 -*-
"""
Gera um _STATUS_PMIB SINTETICO para testes fora do Box (ex.: SIG-FT na nuvem).

Parte de um arquivo real que tem tudo o que o openpyxl apaga — comentarios em
thread e listas suspensas de extensao (x14) — e troca todo texto por texto de
teste: descricoes, codigos, titulos, comentarios, autores. Mantem os nomes de
coluna e os vocabularios (STATUS, COMPLETO, SIM...), as datas e a estrutura
interna do pacote, que e o que interessa testar.

So LE o Box. Uso:
    python _gestao_v2/gerar_fixture_sintetica.py DESTINO.xlsx
"""
from __future__ import annotations

import io
import re
import sys
import zipfile

AQUI = __import__("pathlib").Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "_scripts"))
import regras_sobressalentes as R  # noqa: E402

# Ventilacao das Salas de Baterias U9: 3 comentarios em thread e 2 listas suspensas de extensao (x14) em 04/10/2026
ORIGEM = (R.PASTA_PMIB / "01 - CONTROLE CENTRALIZADO" / "SERVIÇOS AUXILIARES ESSENCIAIS"
          / "SISTEMA DE VENTILAÇÃO DAS SALAS DE BATERIAS U9" / "#ST50=X00XAC21GQ030-GQ905&MPB020_STATUS_PMIB.xlsx")

# textos que ficam: cabecalhos e vocabularios (o resto vira texto de teste)
MANTER = {R.normalizar(t) for t in [
    "ITEM", "QTD.", "UNID.", "DESCRIÇÃO", "CÓDIGO DO MATERIAL", "CÓDIGO CMI", "MARCA/MODELO", "CÓDIGO PMIB",
    "PDM usado", "STATUS", "INFO. GERAIS", "CARACT. TÉCNICAS", "DOCUMENTOS E IMAGENS", "CONDIÇÕES",
    "VALORIZAÇÃO", "APLICAÇÃO - LMR", "DATA DO EMAIL COMUNICANDO ENTREGA", "APTO PARA ENTREGA",
    "EQUIPAMENTO ENTREGUE", "OBSERVAÇÕES", "DADOS VÁLIDOS", "FICHA CRIADA", "DUPLICADO", "COM O FORNECEDOR",
    "EM ELABORAÇÃO", "EM CORREÇÃO", "EM ANÁLISE IB", "APROVADO", "INICIAR", "N/A", "COMPLETO", "INCOMPLETO",
    "SIM", "NÃO", "PÇ", "UN", "-", "Lista de Materiais", "Checklist"]}


def anonimizar_texto(t: str, n: list[int]) -> str:
    if R.normalizar(t) in MANTER:
        return t
    if R.normalizar_pmib(t):
        n[0] += 1
        return f"4500063671.9{n[0]:03d}"
    n[0] += 1
    return f"TEXTO DE TESTE {n[0]}"


def main(destino: str) -> None:
    contador = [0]
    trocar_t = lambda m: m.group(1) + anonimizar_texto(m.group(2), contador) + m.group(3)  # noqa: E731
    buf = io.BytesIO()
    with zipfile.ZipFile(ORIGEM) as zin, zipfile.ZipFile(buf, "w") as zout:
        for info in zin.infolist():
            dados = zin.read(info.filename)
            nome = info.filename
            if nome == "xl/sharedStrings.xml" or nome.startswith("xl/worksheets/sheet"):
                txt = dados.decode("utf-8")
                txt = re.sub(r"(<t(?: [^>]*)?>)([^<]*)(</t>)", trocar_t, txt)           # textos (compartilhados e inline)
                dados = txt.encode("utf-8")
            elif nome.startswith("xl/threadedComments/"):
                dados = re.sub(rb"<text>[^<]*</text>", b"<text>Coment\xc3\xa1rio de teste</text>", dados)
            elif nome.startswith("xl/comments"):
                txt = dados.decode("utf-8")
                # a anotacao-espelho do comentario em thread traz um preambulo fixo e, depois de
                # "Comment:", o texto real — mantem o preambulo, troca o texto
                def legado(m):
                    t = m.group(2)
                    if t.startswith("[Threaded comment]") and "Comment:" in t:
                        t = t.split("Comment:")[0] + "Comment:\n    Comentário de teste"
                    elif not t.startswith("[Threaded comment]"):
                        t = "Comentário de teste"
                    return m.group(1) + t + m.group(3)
                txt = re.sub(r"(<t(?: [^>]*)?>)([^<]*)(</t>)", legado, txt, flags=re.S)
                txt = re.sub(r"<author>[^<]*</author>", "<author>tc=teste</author>", txt)
                dados = txt.encode("utf-8")
            elif nome.startswith("xl/persons/"):
                dados = re.sub(rb'displayName="[^"]*"', b'displayName="Teste"', dados)
                dados = re.sub(rb'userId="[^"]*"', b'userId="teste@exemplo.com"', dados)
            elif nome == "docProps/core.xml":
                dados = re.sub(rb"<dc:creator>[^<]*</dc:creator>", b"<dc:creator>Teste</dc:creator>", dados)
                dados = re.sub(rb"<cp:lastModifiedBy>[^<]*</cp:lastModifiedBy>", b"<cp:lastModifiedBy>Teste</cp:lastModifiedBy>", dados)
            elif nome.startswith("xl/externalLinks/"):
                continue                                                               # nao ha neste arquivo
            zi = zipfile.ZipInfo(nome, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zout.writestr(zi, dados)
    open(destino, "wb").write(buf.getvalue())
    print(f"OK: {destino} ({contador[0]} textos trocados)")


if __name__ == "__main__":
    main(sys.argv[1])
