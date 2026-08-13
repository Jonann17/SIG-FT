r"""
Confere os seletores do projeto contra a tela REAL do portal PMIB.

    python scripts/auditar_seletores.py                  # audita a página aberta
    python scripts/auditar_seletores.py --url <endereco>  # navega antes de auditar

Para que serve: o portal vai ser atualizado, e hoje a única forma de descobrir
o que quebrou é rodar um módulo até ele falhar no meio de um lote -- com o
navegador aberto, uma ficha pela metade e uma mensagem que raramente diz "o
botão X sumiu". Este script inverte isso: em ~10 segundos, sem tocar em ficha
nenhuma, ele diz quais seletores ainda casam com a tela e quais não casam
mais.

Como usar numa atualização do portal:

  1. rode ANTES da atualização e guarde a saída (`> antes.txt`);
  2. rode DEPOIS (`> depois.txt`);
  3. `diff antes.txt depois.txt` -- a lista de seletores a corrigir.

O script é somente-leitura: conta ocorrências, não clica, não digita, não
salva nada no portal. Dá para rodar numa ficha real sem medo.

LIMITES, que são grandes e é melhor saber antes:

  - Ele só enxerga os seletores declarados como CONSTANTE. Hoje isso é 36 dos
    176 do projeto (`upload_conditions` e `ficha_duplicada` têm quase tudo
    inline). Nomear os que faltam é o que faz esta ferramenta valer.
  - Cada página do portal tem só os seus elementos. Um seletor da aba de
    Condições não casa na lista de fichas -- "AUSENTE" aqui significa "não
    está NESTA tela", não necessariamente "quebrou". Por isso a saída separa
    por módulo: rode na tela de cada módulo e olhe o bloco correspondente.
  - Os `XPATH_REL_*` são relativos a uma linha de tabela e não têm sentido
    sozinhos; aparecem marcados e não são conferidos.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sigft.core.rpa import inventario  # noqa: E402


def _engine(url):
    """Abre o motor Playwright com o PERFIL PERSISTENTE -- é o que faz o
    login manual do PMIB continuar valendo entre execuções. Sem isso, cada
    auditoria começaria pela tela de login e não veria seletor nenhum."""
    from sigft.core.rpa.playwright_engine import PlaywrightEngine

    engine = PlaywrightEngine.criar()
    if url:
        engine.goto(url)
    return engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None, help="Endereço a abrir antes de auditar.")
    parser.add_argument(
        "--listar", action="store_true",
        help="Só imprime o inventário, sem abrir navegador (offline).",
    )
    args = parser.parse_args()

    achados = inventario.coletar()
    print("=" * 78)
    print("SIG-FT -- auditoria de seletores do portal")
    print("=" * 78)
    print(f"\n{len(achados)} seletores nomeados no inventário:\n")
    for modulo, quantidade in sorted(inventario.resumo_por_modulo(achados).items()):
        print(f"   {quantidade:3d}  {modulo}")

    repetidos = inventario.duplicados(achados)
    if repetidos:
        print(f"\n{len(repetidos)} seletor(es) declarado(s) em mais de um lugar "
              "-- corrigir um e esquecer o outro é o erro clássico aqui:\n")
        for seletor, locais in repetidos.items():
            print(f"   {seletor}")
            for local in locais:
                print(f"      - {local}")

    if args.listar:
        print("\n(--listar: nenhum navegador foi aberto)")
        return 0

    print("\nAbrindo o navegador (perfil persistente -- o login do PMIB deve "
          "continuar valendo)...")
    engine = _engine(args.url)

    modulo_atual = None
    ausentes = 0
    conferidos = 0
    try:
        print(f"\nPágina auditada: {engine.current_url()}\n")
        for modulo, nome, seletor, relativo in achados:
            if modulo != modulo_atual:
                modulo_atual = modulo
                print(f"\n--- {modulo}")
            if relativo:
                print(f"   [rel]      {nome}  (relativo a uma linha -- não conferível sozinho)")
                continue
            try:
                quantos = engine.contar(seletor)
            except Exception as erro:
                print(f"   [ERRO]     {nome}: {type(erro).__name__}")
                continue
            conferidos += 1
            if quantos == 0:
                ausentes += 1
                print(f"   [AUSENTE]  {nome}")
                print(f"              {seletor}")
            else:
                marca = "OK" if quantos == 1 else f"x{quantos}"
                print(f"   [{marca:8s}] {nome}")
    finally:
        engine.fechar()

    print("\n" + "=" * 78)
    print(f"{conferidos} conferidos nesta tela; {ausentes} não encontrados.")
    print("Lembre-se: 'AUSENTE' pode significar apenas que o elemento não "
          "existe NESTA tela.\nRode na tela de cada módulo e olhe o bloco dele.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
