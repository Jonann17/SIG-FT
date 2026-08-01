r"""
sigft/core/llm/comparacao.py — comparação A/B de modelos de IA.

Ferramenta de VALIDAÇÃO (não faz parte do caminho de execução dos módulos):
existe para atender o Aceite do CP 3.3 do plano de refatoração
(docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.3), que exige que o
usuário "valide a qualidade num punhado de fichas (A/B contra o modelo
anterior)" ANTES de adotar os modelos econômicos do MODELOS_IA.md — e que,
até aqui, não tinha nenhum mecanismo que tornasse isso possível na prática.

Fluxo completo da validação (ver `scripts/ab_modelos.py`, o CLI que usa
este módulo):

  1. `SIGFT_DUMP_PROMPTS=<pasta>` liga a captura de prompts REAIS em
     `core/llm/client.py` — rode um módulo do SIG-FT normalmente uma vez e
     os prompts de verdade (que dependem de ler Excel/PDF) ficam salvos.
  2. `scripts/ab_modelos.py` reexecuta um desses prompts em N modelos.
  3. Este módulo compara as respostas e monta o relatório.

O que ele consegue julgar SOZINHO (e é a maior parte do trabalho chato):
divergência estrutural do JSON — campo que sumiu, campo que apareceu, valor
que mudou, item a mais/a menos numa lista. É exatamente o tipo de erro que
importa nas tarefas mecânicas (`tech_specs`, `categorizar_pdm`,
`validar_ficha`): JSON inválido, TIPO/ACAO trocados, item faltando.

O que ele NÃO julga (e o relatório diz isso explicitamente): se um texto
livre em português/espanhol está BOM. `condicoes` e `autospec` geram prosa
técnica — aí a leitura humana é insubstituível, e o relatório coloca as
respostas lado a lado justamente para facilitar essa leitura.

Só stdlib (`json`) — puro e testável sem rede/SDK nenhum.
"""

from __future__ import annotations

import json

# Quantos caracteres de um valor divergente aparecem no relatório antes de
# ser truncado (respostas de IA podem ter parágrafos inteiros num campo só).
LIMITE_PREVIA_VALOR = 160


def achatar(valor: object, prefixo: str = "") -> dict[str, object]:
    """Achata uma estrutura JSON aninhada num dict `caminho -> valor folha`.

    Caminhos usam ponto para chaves de objeto e colchete para índice de
    lista: `campos_fixos.transporte.status`, `[0].TIPO`, `itens[2].nome`.
    Objetos/listas VAZIOS viram folhas eles mesmos (`{}`/`[]`), para que
    "campo virou vazio" apareça como diferença em vez de sumir da comparação.
    """
    if isinstance(valor, dict) and valor:
        achatado: dict[str, object] = {}
        for chave, sub in valor.items():
            caminho = f"{prefixo}.{chave}" if prefixo else str(chave)
            achatado.update(achatar(sub, caminho))
        return achatado

    if isinstance(valor, list) and valor:
        achatado = {}
        for indice, sub in enumerate(valor):
            achatado.update(achatar(sub, f"{prefixo}[{indice}]"))
        return achatado

    return {prefixo or "(raiz)": valor}


def comparar_json(baseline: object, candidato: object) -> dict[str, object]:
    """Compara duas respostas JÁ PARSEADAS e resume as diferenças.

    Devolve um dict com:
      `iguais`: `True` se não há nenhuma diferença estrutural nem de valor.
      `so_no_baseline` / `so_no_candidato`: caminhos presentes só de um lado
        (campo que sumiu / campo inventado — o sintoma mais comum de um
        modelo mais fraco).
      `valores_diferentes`: lista de `{caminho, baseline, candidato}`.
      `total_diferencas`: soma das três listas acima, para ordenar/resumir.

    Não julga QUALIDADE de texto livre: um campo de prosa reescrito com
    outras palavras conta como "valor diferente" sem que isso signifique
    "pior". É o relatório que deixa esse limite explícito para quem lê.
    """
    plano_base = achatar(baseline)
    plano_cand = achatar(candidato)

    caminhos_base = set(plano_base)
    caminhos_cand = set(plano_cand)

    diferentes = [
        {"caminho": caminho, "baseline": plano_base[caminho], "candidato": plano_cand[caminho]}
        for caminho in sorted(caminhos_base & caminhos_cand)
        if plano_base[caminho] != plano_cand[caminho]
    ]
    so_base = sorted(caminhos_base - caminhos_cand)
    so_cand = sorted(caminhos_cand - caminhos_base)

    return {
        "iguais": not (diferentes or so_base or so_cand),
        "so_no_baseline": so_base,
        "so_no_candidato": so_cand,
        "valores_diferentes": diferentes,
        "total_diferencas": len(diferentes) + len(so_base) + len(so_cand),
    }


def _previa(valor: object) -> str:
    """Representação curta e de uma linha só de um valor, para caber na
    tabela/lista do relatório sem quebrar o markdown."""
    if isinstance(valor, str):
        texto = valor
    else:
        texto = json.dumps(valor, ensure_ascii=False)
    texto = " ".join(texto.split())  # colapsa quebras de linha
    if len(texto) > LIMITE_PREVIA_VALOR:
        texto = texto[:LIMITE_PREVIA_VALOR] + "…"
    return texto.replace("|", "\\|")  # não quebrar a tabela markdown


def _fmt_custo(custo: float | None) -> str:
    return "—" if custo is None else f"US$ {custo:.6f}"


def _fmt_tokens(entrada: int | None, saida: int | None) -> str:
    if entrada is None and saida is None:
        return "—"
    return f"{entrada if entrada is not None else '?'} / {saida if saida is not None else '?'}"


def montar_relatorio_markdown(
    resultados: list[dict[str, object]], *, contexto: dict[str, object] | None = None
) -> str:
    """Monta o relatório A/B em markdown a partir dos resultados brutos.

    Cada item de `resultados` é um dict com: `rotulo` (ex.
    `"openrouter:x-ai/grok-4.5"`), `ok` (bool), e — quando `ok` — `texto`,
    `parsed` (JSON já parseado ou `None` se não parseou), `tokens_in`,
    `tokens_out`, `custo_usd`, `duracao_s`; quando não `ok`, `erro` (str).
    O PRIMEIRO item é tratado como BASELINE (o modelo atual, contra o qual
    os outros são comparados) — é a convenção do `scripts/ab_modelos.py`.
    """
    if not resultados:
        return "# Comparação A/B de modelos\n\n_Nenhum resultado._\n"

    contexto = contexto or {}
    linhas: list[str] = ["# Comparação A/B de modelos", ""]

    if contexto:
        for rotulo, valor in contexto.items():
            linhas.append(f"- **{rotulo}**: {valor}")
        linhas.append("")

    baseline = resultados[0]
    linhas.append(f"Baseline (referência de comparação): **{baseline['rotulo']}**")
    linhas.append("")

    # --- 1. Tabela-resumo ---------------------------------------------
    linhas += [
        "## Resumo",
        "",
        "| Modelo | Status | JSON válido | Tokens (in/out) | Custo | Duração | Difs. vs baseline |",
        "|---|---|---|---|---|---|---|",
    ]

    comparacoes: dict[str, dict[str, object]] = {}
    for indice, resultado in enumerate(resultados):
        rotulo = str(resultado["rotulo"])
        if not resultado.get("ok"):
            linhas.append(f"| `{rotulo}` | ❌ falhou | — | — | — | — | — |")
            continue

        parsed = resultado.get("parsed")
        json_ok = "✅" if parsed is not None else "❌"

        if indice == 0:
            difs = "(baseline)"
        elif parsed is None or baseline.get("parsed") is None:
            difs = "n/d"
        else:
            comparacao = comparar_json(baseline["parsed"], parsed)
            comparacoes[rotulo] = comparacao
            total = comparacao["total_diferencas"]
            difs = "✅ idêntico" if comparacao["iguais"] else f"⚠️ {total}"

        duracao = resultado.get("duracao_s")
        duracao_fmt = f"{duracao:.1f}s" if isinstance(duracao, (int, float)) else "—"
        tokens_fmt = _fmt_tokens(resultado.get("tokens_in"), resultado.get("tokens_out"))
        linhas.append(
            f"| `{rotulo}` | ✅ ok | {json_ok} | {tokens_fmt} "
            f"| {_fmt_custo(resultado.get('custo_usd'))} | {duracao_fmt} | {difs} |"
        )

    # --- 2. Falhas -----------------------------------------------------
    falhas = [r for r in resultados if not r.get("ok")]
    if falhas:
        linhas += ["", "## Falhas", ""]
        for resultado in falhas:
            linhas.append(f"- **`{resultado['rotulo']}`**: {resultado.get('erro')}")

    # --- 3. Diferenças detalhadas --------------------------------------
    if comparacoes:
        linhas += ["", "## Diferenças em relação ao baseline", ""]
        for rotulo, comparacao in comparacoes.items():
            linhas += [f"### `{rotulo}`", ""]
            if comparacao["iguais"]:
                linhas += ["JSON idêntico ao do baseline.", ""]
                continue

            if comparacao["so_no_baseline"]:
                linhas.append("**Campos que sumiram** (existem no baseline, faltam aqui):")
                linhas += [f"- `{c}`" for c in comparacao["so_no_baseline"]]
                linhas.append("")
            if comparacao["so_no_candidato"]:
                linhas.append("**Campos a mais** (não existem no baseline):")
                linhas += [f"- `{c}`" for c in comparacao["so_no_candidato"]]
                linhas.append("")
            if comparacao["valores_diferentes"]:
                linhas += [
                    "**Valores diferentes:**",
                    "",
                    "| Campo | Baseline | Este modelo |",
                    "|---|---|---|",
                ]
                for dif in comparacao["valores_diferentes"]:
                    linhas.append(
                        f"| `{dif['caminho']}` | {_previa(dif['baseline'])} "
                        f"| {_previa(dif['candidato'])} |"
                    )
                linhas.append("")

    # --- 4. Respostas completas ----------------------------------------
    linhas += ["", "## Respostas completas", ""]
    for resultado in resultados:
        linhas += [f"### `{resultado['rotulo']}`", ""]
        if not resultado.get("ok"):
            linhas += [f"_Falhou: {resultado.get('erro')}_", ""]
            continue
        # Cerca de 4 crases: a resposta CRUA da IA frequentemente já vem com
        # ```json dentro, e uma cerca de 3 aninhada quebraria a renderização
        # do markdown (CommonMark: a cerca externa precisa ser mais longa).
        linhas += ["````", str(resultado.get("texto", "")).strip(), "````", ""]

    # --- 5. Limite honesto da ferramenta -------------------------------
    linhas += [
        "---",
        "",
        "> **O que este relatório NÃO decide por você.** A contagem de diferenças mede",
        "> divergência ESTRUTURAL do JSON (campo que sumiu, valor que mudou) — ótimo para",
        "> `tech_specs`, `categorizar_pdm` e `validar_ficha`, onde o certo e o errado são",
        "> objetivos. Para `condicoes` e `autospec`, boa parte do conteúdo é texto técnico",
        "> livre em PT/ES: um valor \"diferente\" pode estar igualmente correto, ou melhor.",
        "> Nesses casos use as respostas completas acima e leia. Em especial, confira",
        "> tradução PT→ES e termos técnicos — é o ponto que o MODELOS_IA.md marca como não",
        "> verificado para os modelos mais baratos.",
        "",
    ]

    return "\n".join(linhas) + "\n"
