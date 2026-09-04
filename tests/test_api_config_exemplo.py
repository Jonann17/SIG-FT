# -*- coding: utf-8 -*-
"""O modelo do `api_config.json` — que existe porque o real nunca sobe.

O `api_config.json` é ignorado pelo git DE PROPÓSITO: chave não sobe a
repositório. A consequência é que quem clona (ou baixa o ZIP do GitHub) não
tem como saber quais chaves o app espera — o arquivo simplesmente não está
lá, e nada no repositório dizia o que ele deveria conter.

Isto ficou urgente em 2026-09-04, quando o usuário passou a trabalhar só pelo
GitHub e apagar a cópia local: o único lugar onde a forma do arquivo existia
era a máquina dele.
"""
import json
import pathlib

from sigft import config

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MODELO = RAIZ / "api_config.example.json"


def _modelo():
    return json.loads(MODELO.read_text(encoding="utf-8"))


def test_o_modelo_existe():
    assert MODELO.exists(), (
        "sem o modelo, quem clona o repositorio nao descobre quais chaves o "
        "app espera -- o api_config.json real nunca sobe"
    )


def test_o_modelo_cobre_todas_as_chaves_que_o_codigo_le():
    """Chave nova em `ENV_VAR_POR_CHAVE` tem que aparecer no modelo.

    Sem isto o modelo apodrece em silêncio: o código passa a exigir uma chave
    que o modelo não menciona, e quem monta o ambiente do zero descobre pelo
    erro em produção.
    """
    modelo = _modelo()

    faltando = sorted(set(config.ENV_VAR_POR_CHAVE) - set(modelo))

    assert not faltando, (
        f"o codigo le estas chaves e o modelo nao as menciona: {faltando}. "
        f"Acrescente-as em api_config.example.json."
    )


def test_o_modelo_nao_contem_valor_nenhum():
    """A trava que impede um segredo de vazar por descuido.

    O modelo mora no repositório público-para-a-equipe. Se alguém copiar o
    `api_config.json` real por cima dele "para atualizar os campos", as chaves
    sobem junto. Aqui todo campo de chave tem que estar VAZIO.

    Os campos iniciados por `_` são comentários e a explicação de cada
    variável de ambiente — texto, nunca segredo.
    """
    com_valor = [
        chave
        for chave, valor in _modelo().items()
        if not chave.startswith("_") and valor not in ("", {}, [], None)
    ]

    assert not com_valor, (
        f"api_config.example.json tem VALOR nestes campos: {com_valor}. "
        f"O modelo carrega os nomes, nunca os valores -- isto e um vazamento."
    )


def test_o_modelo_diz_qual_variavel_de_ambiente_corresponde():
    """Cada chave tem uma env var de nome diferente (GEMINI ->
    API_GEMINI_LUAN_GMAIL). Sem essa correspondência escrita, quem configura
    por variável de ambiente tem que ler o código."""
    texto = MODELO.read_text(encoding="utf-8")

    faltando = [
        env_var
        for env_var in config.ENV_VAR_POR_CHAVE.values()
        if env_var not in texto
    ]

    assert not faltando, f"o modelo nao cita as variaveis: {faltando}"
