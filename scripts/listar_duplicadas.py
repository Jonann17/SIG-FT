r"""
Lista as fichas DUPLICADAS de um `_STATUS_PMIB` — sem tocar no portal.

    python scripts/listar_duplicadas.py caminho\para\4500063671_STATUS_PMIB.xlsx

Por que existe: a Fase 6 constrói o robô de duplicação em cima de uma pergunta
só — *"quais fichas são duplicadas, e o que a planilha sabe sobre cada uma?"*.
Se essa resposta estiver errada, tudo o que vier depois erra em cima dela, e o
erro só apareceria com o navegador aberto, no meio de um lote.

Este script responde a pergunta em segundos, contra a SUA planilha real, sem
abrir navegador, sem tocar no PMIB e sem alterar o arquivo. É leitura pura.

O que conferir na saída:

  - a **contagem** bate com o que você espera dessa planilha?
  - os **PMIB** listados são mesmo as duplicadas?
  - a **ficha original** de cada uma está certa (vem de OBSERVAÇÕES)?
  - a **referência do fabricante** (CÓDIGO DO MATERIAL) está preenchida?
  - as **impedidas** estão impedidas por um motivo que faz sentido?
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sigft.services import duplicadas  # noqa: E402


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    caminho = argv[1]
    if not os.path.isfile(caminho):
        print(f"Arquivo não encontrado: {caminho}")
        return 1

    print("=" * 78)
    print("SIG-FT -- fichas duplicadas no _STATUS_PMIB")
    print("=" * 78)
    print(f"\nArquivo: {os.path.basename(caminho)}\n")

    fichas, mensagem = duplicadas.localizar_duplicadas(caminho, callback_log=print)
    print(mensagem)

    if not fichas:
        print("\nNenhuma ficha marcada como duplicada.")
        print("Se você esperava alguma, confira a coluna do PDM usado: o valor")
        print(f"tem de começar com {duplicadas.spec.PDM_DUPLICADA}")
        return 0

    prontas = [f for f in fichas if f.pronta_para_duplicar]
    impedidas = [f for f in fichas if not f.pronta_para_duplicar]

    if prontas:
        print(f"\n--- PRONTAS PARA O ROBÔ ({len(prontas)})\n")
        print(f"   {'linha':>6}  {'PMIB':22} {'ficha original':18} {'ref. fabricante':18} ref. fornecedor")
        print("   " + "-" * 92)
        for ficha in prontas:
            print(
                f"   {ficha.linha:>6}  {ficha.pmib:22} {ficha.ficha_original:18} "
                f"{ficha.codigo_material:18} {ficha.codigo_fornecedor or '(vazio -- será ignorado)'}"
            )

    if impedidas:
        print(f"\n--- IMPEDIDAS ({len(impedidas)}) -- faltam dados na planilha\n")
        for ficha in impedidas:
            print(f"   linha {ficha.linha}: {ficha.pmib or '(sem código PMIB)'}")
            print(f"      falta: {ficha.motivo_de_impedimento}")

    print("\n" + "=" * 78)
    print("Nada foi alterado: este script só LÊ a planilha.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
