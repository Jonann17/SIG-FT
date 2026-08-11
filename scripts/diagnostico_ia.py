r"""
Diagnóstico da camada de IA — responde "qual modelo, qual provedor, qual chave"
para cada tarefa, sem chamar a API.

    python scripts/diagnostico_ia.py

Nada é enviado para lugar nenhum e nenhuma chave aparece inteira na tela (só o
começo e o fim, o suficiente para você reconhecer qual é).

Por que existe: quando a IA falha com "API key not valid", há três suspeitos
diferentes e a mensagem do Google não distingue entre eles —

  1. a chave não chegou (vazia, ou lida de um lugar e configurada em outro);
  2. a chave chegou, mas o MODELO resolvido não é o que você imagina (o painel
     "Modelos de IA" da Home grava uma seleção que vence o padrão do código);
  3. a chave e o modelo estão certos, e o problema é a conta do Google.

Este script separa os três em dez segundos.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sigft import config  # noqa: E402
from sigft.core.llm import selecao  # noqa: E402


def _mascarar(valor):
    """Mostra o bastante para reconhecer a chave, nunca a chave."""
    if valor is None:
        return "AUSENTE (None)"
    if valor == "":
        return "VAZIA ('')"
    texto = str(valor)
    if len(texto) <= 10:
        return f"{'*' * len(texto)}  ({len(texto)} caracteres)"
    return f"{texto[:6]}...{texto[-4:]}  ({len(texto)} caracteres)"


def main() -> int:
    print("=" * 72)
    print("SIG-FT -- diagnostico da camada de IA")
    print("=" * 72)

    # ---------------------------------------------------------------- chaves
    print("\n1. CHAVES (de onde cada uma veio)\n")
    caminho_cfg = config.CONFIG_FILE
    existe_cfg = os.path.isfile(caminho_cfg)
    print(f"   {caminho_cfg}: {'existe' if existe_cfg else 'NAO existe'}")
    print(f"   .env na raiz: {'existe' if os.path.isfile('.env') else 'NAO existe'}")
    print()

    chaves = config.carregar_chaves()
    for nome_logico, env_var in sorted(config.ENV_VAR_POR_CHAVE.items()):
        valor = chaves.get(nome_logico)
        origem = []
        if os.environ.get(env_var):
            origem.append(f"env {env_var}")
        if existe_cfg:
            try:
                with open(caminho_cfg, encoding="utf-8") as arquivo:
                    if json.load(arquivo).get(nome_logico):
                        origem.append("api_config.json")
            except Exception:
                pass
        print(f"   {nome_logico:22s} {_mascarar(valor):32s} {' + '.join(origem) or '(nenhuma fonte)'}")

    # -------------------------------------------------------------- modelos
    print("\n2. MODELO RESOLVIDO POR TAREFA\n")
    print(f"   {'tarefa':16s} {'provider':12s} {'modelo':28s} origem")
    print("   " + "-" * 68)
    for tarefa in sorted(config.LLM_MODELOS_HOJE):
        try:
            resolvido = selecao.resolver(tarefa, config_path=caminho_cfg)
        except Exception as erro:
            print(f"   {tarefa:16s} ERRO ao ler a selecao: {type(erro).__name__}: {erro}")
            continue

        if resolvido is None:
            cfg = config.LLM_MODELOS_HOJE[tarefa]
            origem = "padrao do codigo"
        else:
            cfg = resolvido
            origem = "SELECAO salva no painel 'Modelos de IA'"

        print(f"   {tarefa:16s} {cfg['provider']:12s} {cfg['model']:28s} {origem}")

    # ------------------------------------------------- chave que cada tarefa usa
    print("\n3. CHAVE QUE CADA TAREFA VAI USAR\n")
    print("   (o app passa a chave Gemini explicitamente; as demais saem das chaves acima)")
    print()
    for tarefa in sorted(config.LLM_MODELOS_HOJE):
        resolvido = selecao.resolver(tarefa, config_path=caminho_cfg)
        cfg = resolvido if resolvido is not None else config.LLM_MODELOS_HOJE[tarefa]
        provider = cfg["provider"]
        nome_chave = config.CHAVE_POR_PROVIDER.get(provider)
        if nome_chave is None:
            print(f"   {tarefa:16s} provider {provider!r} NAO TEM implementacao -- vai falhar")
            continue
        print(f"   {tarefa:16s} usa a chave {nome_chave:14s} {_mascarar(chaves.get(nome_chave))}")

    # ---------------------------------------------------------------- leitura
    print("\n" + "=" * 72)
    print("COMO LER ISTO")
    print("=" * 72)
    print("""
 - Chave VAZIA ou AUSENTE na tarefa que falhou  -> a chave nao chegou. Configure
   pela tela Home do app (grava em api_config.json) OU no .env da raiz.

 - Modelo com origem "SELECAO salva" e diferente do que voce esperava -> alguem
   (ou um clique em "Aplicar recomendados") gravou uma escolha no painel
   "Modelos de IA" da Home. Ela vence o padrao do codigo. Para voltar ao padrao,
   apague a entrada "_modelos_ia" do api_config.json.

 - Chave presente, modelo o esperado, e a API ainda recusa -> o problema esta na
   conta do Google: a chave pode nao ter a Generative Language API habilitada,
   ou nao ter acesso AQUELE modelo. Teste o mesmo modelo no Google AI Studio com
   a mesma chave.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
