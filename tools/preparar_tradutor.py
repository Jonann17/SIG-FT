"""Prepara o modelo do tradutor local (Tradutor 4.2) para ir no instalador.

Rodado pelo workflow de release ANTES dos testes e do PyInstaller, e à mão por
quem roda o SIG-FT pelo código-fonte:

    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install "transformers<5" huggingface_hub ctranslate2 sentencepiece
    python tools/preparar_tradutor.py

Baixa o OPUS-MT `tc-big-itc-itc` do Hugging Face NA REVISÃO FIXA abaixo,
converte para CTranslate2 em int8 e grava em `recursos/tradutor_pt_es/`, que
o `SIG-FT.spec` embute como `modelos/tradutor_pt_es`. `torch` e
`transformers` só são necessários AQUI: o app, em execução, usa só
`ctranslate2` e `sentencepiece` (`sigft/core/tradutor_local.py`).

    python tools/preparar_tradutor.py --verificar     # 0 se a pasta serve

A pasta é pesada (~218 MB) e está no `.gitignore`: nunca vai para o Git.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from sigft.core import tradutor_local  # noqa: E402

MODELO_HF = "Helsinki-NLP/opus-mt-tc-big-itc-itc"
# Revisão FIXA: um `main` que muda sozinho mudaria a tradução das fichas sem
# ninguém ver. Trocar é decisão, com o experimento refeito
# (docs/superpowers/specs/2026-09-25-tradutor-local-design.md).
REVISAO = "a185ba7b3cac07bbd692dd517577b8c2dc7abb2c"
QUANTIZACAO = "int8"
DESTINO_PADRAO = RAIZ / "recursos" / tradutor_local.NOME_DA_PASTA

# O que vem do Hugging Face além dos pesos: os dois tokenizadores (o app
# precisa) e o README, que traz a licença CC-BY 4.0 e a citação.
_DO_HF = ("source.spm", "target.spm", "README.md")

LEIA_ME = f"""\
Tradutor local do SIG-FT (PT -> ES)

Modelo: {MODELO_HF} (revisao {REVISAO})
Autores: Helsinki-NLP / Language Technology Research Group, Universidade de
Helsinque (projeto OPUS-MT / Tatoeba Translation Challenge).
Licenca: CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
Alteracao: convertido para CTranslate2 com quantizacao {QUANTIZACAO}, sem
retreino. O README.md desta pasta e o original do autor.
"""


def _baixar(modelo: str, revisao: str) -> Path:
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(modelo, revision=revisao))


def _converter(origem, destino, quantizacao: str) -> None:
    import ctranslate2

    ctranslate2.converters.TransformersConverter(str(origem)).convert(
        str(destino), quantization=quantizacao, force=True)


def preparar(destino=DESTINO_PADRAO, *, baixar=_baixar, converter=_converter) -> Path:
    """Gera a pasta do modelo. Se ela já está completa, não faz nada.

    Converte numa pasta `.tmp` e só troca no fim: uma conversão que falha no
    meio (memória, rede) não deixa uma pasta pela metade que o app aceitaria.
    """
    destino = Path(destino)
    if tradutor_local.modelo_completo(destino):
        print(f"Modelo ja preparado em {destino}")
        return destino

    origem = baixar(MODELO_HF, REVISAO)
    temporaria = destino.with_name(destino.name + ".tmp")
    shutil.rmtree(temporaria, ignore_errors=True)
    try:
        converter(origem, temporaria, QUANTIZACAO)
        for nome in _DO_HF:
            shutil.copy2(Path(origem) / nome, temporaria / nome)
        (temporaria / "origem.json").write_text(json.dumps({
            "modelo": MODELO_HF,
            "revisao": REVISAO,
            "quantizacao": QUANTIZACAO,
            "licenca": "CC-BY 4.0 (Helsinki-NLP, OPUS-MT)",
        }, indent=1, ensure_ascii=False), encoding="utf-8")
        (temporaria / "LEIA-ME.txt").write_text(LEIA_ME, encoding="utf-8")
        if not tradutor_local.modelo_completo(temporaria):
            raise RuntimeError(f"a conversao nao gerou {tradutor_local.ARQUIVOS_DO_MODELO}")
        shutil.rmtree(destino, ignore_errors=True)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporaria.rename(destino)
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)
    print(f"Modelo preparado em {destino}")
    return destino


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destino", default=str(DESTINO_PADRAO))
    parser.add_argument("--verificar", action="store_true",
                        help="so confere se a pasta esta completa (0 = sim)")
    args = parser.parse_args(argv)
    if args.verificar:
        pronto = tradutor_local.modelo_completo(args.destino)
        print(f"{'OK' if pronto else 'INCOMPLETO'}: {args.destino}")
        return 0 if pronto else 1
    preparar(args.destino)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
