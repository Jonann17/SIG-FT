"""A coluna "APLICAÇÃO - LMR" do `_STATUS_PMIB` — escrita por UM lugar só.

Os dois módulos de LMR mexem na MESMA coluna, em sentidos opostos:

* **Aplicação LMR** (`services/lmr.py`) escreve `COMPLETO` quando a ficha foi
  inteira, `INCOMPLETO` quando ficou pela metade;
* **Apagar Aplicação LMR** (`services/apagar_lmr.py`) LIMPA a célula quando a
  exclusão dá certo — a ficha volta a parecer não-feita, que é a verdade
  depois de apagar as aplicações.

Antes deste módulo (2026-08-28) a escrita existia só no `lmr.py`. Colocar a
segunda cópia no `apagar_lmr.py` seria criar exatamente a duplicação que a
refatoração passou 9 fases eliminando — e as duas divergiriam no primeiro
detalhe que mudasse (o alias de cabeçalho, a mensagem de erro, o retry).

Nenhum dos dois serviços importa o outro: ambos importam daqui.

Por que este módulo não sabe de RPA
------------------------------------
Ele só mexe em planilha. Isso o torna testável sem portal, sem navegador e sem
rede — que é o oposto do resto dos dois módulos, onde nada se prova offline.
"""
from __future__ import annotations

from sigft import config

# Os três valores que a coluna pode receber. `LIMPAR` é string vazia de
# propósito: o usuário pediu que a exclusão "deletasse da coluna o completo e
# deixasse em branco", e vazio é diferente de "INCOMPLETO" — uma ficha cujas
# aplicações foram apagadas não está incompleta, está por fazer.
COMPLETO = "COMPLETO"
INCOMPLETO = "INCOMPLETO"
LIMPAR = ""


def cabecalhos_da_linha(painel) -> str:
    """Os textos da linha de cabeçalho, para a mensagem de erro poder DIZER o
    que a planilha tem — em vez de só reclamar do que ela não tem."""
    try:
        linha = painel.header_row or 1
        valores = [
            str(painel.ws.cell(row=linha, column=c).value or "").strip()
            for c in range(1, 50)
        ]
        return ", ".join(f"'{v}'" for v in valores if v) or "(nenhum)"
    except Exception:  # noqa: BLE001
        return "(não consegui ler)"


def escrever(
    caminho_status,
    alvos,
    *,
    retry_lock=None,
    callback_log=None,
):
    """Escreve a coluna "APLICAÇÃO - LMR" para as fichas de `alvos`.

    `alvos` é uma sequência de pares `(pmib, valor)`. O `valor` vai para a
    célula como está — use `COMPLETO`, `INCOMPLETO` ou `LIMPAR`.

    Devolve `(quantidade_escrita, mensagem)`. **Nunca levanta por causa da
    planilha**: uma falha aqui não pode apagar o trabalho que o robô já fez no
    portal, que é a parte cara e não repetível. Quem chama decide o que fazer
    com a mensagem.
    """
    from sigft.core.excel import status_sheet

    alvos = list(alvos)
    if not alvos:
        return 0, "Nenhuma ficha para marcar no _STATUS_PMIB."

    def _log(msg):
        if callback_log:
            callback_log(msg)

    try:
        painel = status_sheet.StatusPMIB(caminho_status, config.ABA_LISTA_MATERIAIS)
        # A coluna de LMR entra com TODOS os aliases apontando para a MESMA
        # chave de saída -- é o recurso que `find_columns` oferece para
        # cabeçalho com grafia variável (ver config.ALIASES_COL_APLICACAO_LMR).
        painel.abrir(
            keywords={
                config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
                config.COL_APLICACAO_LMR: config.ALIASES_COL_APLICACAO_LMR,
            },
            # `required` só o código: a varredura não pode parar por não achar
            # a coluna de LMR -- precisamos chegar ao fim para poder LISTAR os
            # cabeçalhos que existem, que é o que ajuda quem for corrigir.
            required=[config.COL_CODIGO_PMIB],
            max_row=15,
            max_col=49,
        )
    except Exception as erro:  # noqa: BLE001 -- planilha não pode derrubar o lote
        return 0, f"Não consegui abrir o _STATUS_PMIB: {type(erro).__name__}: {erro}"

    if config.COL_APLICACAO_LMR not in painel.col_map:
        encontrados = cabecalhos_da_linha(painel)
        painel.fechar()
        return 0, (
            f"A coluna '{config.COL_APLICACAO_LMR}' não foi encontrada no _STATUS_PMIB "
            f"-- nada foi marcado.\n"
            f"      Cabeçalhos que existem na planilha: {encontrados}\n"
            f"      Se o nome certo for um destes, me diga qual e eu ajusto "
            f"(config.ALIASES_COL_APLICACAO_LMR)."
        )

    header_row = painel.header_row if painel.header_row is not None else 1
    escritas, nao_achadas = 0, []

    for pmib, valor in alvos:
        linha = painel.buscar_linha(str(pmib).strip(), header_row=header_row)
        if linha is None:
            nao_achadas.append(str(pmib))
            continue
        painel.marcar_linha(linha, {config.COL_APLICACAO_LMR: True}, valor=valor)
        escritas += 1
        _log(
            f"   Planilha: {pmib} -> {config.COL_APLICACAO_LMR} = "
            + (f"{valor}" if valor else "(em branco)")
        )

    if not escritas:
        painel.fechar()
        return 0, (
            "Nenhuma das fichas do lote foi encontrada no _STATUS_PMIB "
            f"(procurei {len(alvos)}). Nada foi salvo."
        )

    # O salvamento passa pelo canal do CP D: com a planilha aberta no Excel, o
    # usuário vê a janela "feche o arquivo e tente de novo" em vez de perder a
    # marcação em silêncio.
    try:
        painel.salvar(
            on_locked=lambda _tent, _exc: bool(retry_lock(caminho_status))
            if retry_lock
            else False
        )
    except PermissionError:
        painel.fechar()
        return 0, (
            "O _STATUS_PMIB está aberto no Excel e a marcação NÃO foi salva. "
            "O trabalho no portal está feito -- feche a planilha e rode de novo "
            "só para marcar, ou marque à mão."
        )
    except Exception as erro:  # noqa: BLE001
        painel.fechar()
        return 0, f"Não consegui salvar o _STATUS_PMIB: {type(erro).__name__}: {erro}"

    painel.fechar()

    recado = f"{escritas} linha(s) marcada(s) no _STATUS_PMIB."
    if nao_achadas:
        recado += (
            f" {len(nao_achadas)} ficha(s) não foram encontradas na planilha: "
            f"{', '.join(nao_achadas[:5])}"
            + ("…" if len(nao_achadas) > 5 else "")
        )
    return escritas, recado


# ---------------------------------------------------------------------------
# Os dois sentidos, nomeados
# ---------------------------------------------------------------------------
def marcar_aplicacao(caminho_status, completas, incompletas, **kwargs):
    """Sentido da APLICAÇÃO: `COMPLETO` para as inteiras, `INCOMPLETO` para as
    que ficaram pela metade.

    Marcar o fracasso é decisão do usuário e é informação: uma ficha que o robô
    mexeu e deixou incompleta precisa aparecer na planilha, senão ela se
    confunde com uma que ninguém tocou.
    """
    alvos = [(p, COMPLETO) for p in completas]
    alvos += [(p, INCOMPLETO) for p in incompletas]
    return escrever(caminho_status, alvos, **kwargs)


def limpar_aplicacao(caminho_status, apagadas, **kwargs):
    """Sentido da EXCLUSÃO: limpa a célula das fichas cujas aplicações foram
    apagadas com sucesso.

    Só as que deram certo. Limpar a marcação de uma ficha cuja exclusão falhou
    diria que ela está por fazer quando as aplicações continuam lá — o pior dos
    dois erros possíveis aqui.
    """
    return escrever(caminho_status, [(p, LIMPAR) for p in apagadas], **kwargs)
