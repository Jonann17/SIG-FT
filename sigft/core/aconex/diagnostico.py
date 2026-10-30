"""O diagnóstico do Aconex: prova quais buscas do register funcionam (portão G1 do
plano), numa máquina com o cofre do DocManager.

    python -m sigft.core.aconex.diagnostico "<código de uma lista>" [--perfil NOME]

Imprime uma linha por sonda: login, register inteiro, busca exata do código, busca
pelo Tracking ID, busca por título e as listas novas que ela traz (o PB020 se
confere aqui: o Aconex devolve HTTP 500 ao coringa no código), uma tentativa por sintaxe do
`search_query` documentada no Documents API Developer Guide
(help.aconex.com/apis/api-guide-documents/, List Documents). Cada sonda lê só a
página 1 e o `TotalResults`, como a sonda `tools/probe_download_aconex.py` do
DocManager; o register inteiro é a referência: uma sintaxe que o Aconex ignore
devolve o register todo e não passa. O `detalhe` traz só contagens e status HTTP,
nunca título nem dado de documento. Desenho:
`docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §4.2.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from sigft.core import prefs
from sigft.core.aconex.cliente import ClienteAconex, ErroAconex, Pagina
from sigft.core.aconex.credenciais import PREFERENCIA_PERFIL, caminho_do_cofre, escolher_perfil, ler_perfis

CAMPOS = "docno,trackingId"
SINTAXES_DO_TRACKING_ID = ("trackingid:{id}", 'trackingid:"{id}"')
# [2026-10-27] Teste do Luan na GE (1.3.1-rc.2): `docno:*PB020*` volta HTTP 500 em
# 5 de 5 tentativas; `title:SOBRESSALENTES` filtra (96 de 9819). O Aconex não
# aceita o coringa no código, e não precisa: a lista nova exige SOBRESSALENTES no
# título, então a busca por título traz todas, e o PB020 (com o "sem PREÇO") se
# confere no SIG-FT, pela mesma regra do Gestão PMIB (`e_lista_de_sobressalentes`).
ROTULO_TITULO, BUSCA_POR_TITULO = "Busca por título", "title:SOBRESSALENTES"
CAMPOS_DO_TITULO = "docno,title,trackingId"
PAGINA_DO_TITULO = 500   # as ~100 listas cabem na página 1 (o register aceita até 500)
SONDA_LISTAS_NOVAS = "Listas novas (PB020 no código, conferido no SIG-FT)"
# Uma sonda prova sintaxe: um HTTP 500 de sintaxe não passa esperando 5, 15, 30 e
# 60 s (no log do Luan, quase 2 min numa sonda só). Duas tentativas ainda cobrem
# a queda de rede passageira.
TENTATIVAS_DO_DIAGNOSTICO = 2


@dataclass(frozen=True)
class Sonda:
    nome: str
    ok: bool
    detalhe: str


def _contar(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _falha(erro: Exception) -> str:
    """O texto do `ErroAconex` (feito para o usuário, sem segredo nem dado de
    documento) ou só o tipo de um erro inesperado, cuja mensagem pode trazer dado."""
    if isinstance(erro, ErroAconex):
        return str(erro)
    return f"erro inesperado ({type(erro).__name__})"


def _pagina(cliente: ClienteAconex, consulta: str, historico: bool, *, campos: str = CAMPOS,
            page_size: int | None = None) -> tuple[Pagina | None, str]:
    """A página 1 da busca, ou `None` e o texto da falha."""
    extra = {"page_size": page_size} if page_size else {}
    try:
        return cliente.primeira_pagina(consulta, historico=historico, campos=campos, **extra), ""
    except Exception as erro:  # noqa: BLE001 -- o diagnóstico relata, não derruba
        return None, _falha(erro)


def _quantos(pagina: Pagina) -> int:
    return pagina.total if pagina.total is not None else len(pagina.registros)


def _sonda_de_filtro(nome: str, pagina: Pagina | None, falha: str, total: int | None, descrever) -> Sonda:
    """Passa quando a busca trouxe algo e menos que o register inteiro."""
    if pagina is None:
        return Sonda(nome, False, falha)
    n = _quantos(pagina)
    if n == 0:
        return Sonda(nome, False, "nenhum documento")
    if total is not None and n >= total:
        return Sonda(nome, False, f"{descrever(n)}: a sintaxe não filtrou")
    return Sonda(nome, True, descrever(n))


def sondar(cliente: ClienteAconex, codigo: str) -> list[Sonda]:
    """As sondas, nesta ordem: login, register inteiro, busca exata, Tracking ID e as
    buscas das listas. Sem login, para; sem a busca exata, pula só as do Tracking ID,
    que saem dela."""
    try:
        cliente.conectar()
    except Exception as erro:  # noqa: BLE001 -- o diagnóstico relata, não derruba
        return [Sonda("Login no Aconex", False, _falha(erro))]
    sondas = [Sonda("Login no Aconex", True, "token recebido")]

    tudo, falha = _pagina(cliente, "", historico=False)
    total = None
    if tudo is None:
        sondas.append(Sonda("Register inteiro (busca vazia)", False, falha))
    else:
        total = _quantos(tudo)
        aviso = " (sem TotalResults: só a 1ª página)" if tudo.total is None else ""
        sondas.append(Sonda("Register inteiro (busca vazia)", True,
                            _contar(total, "documento", "documentos") + aviso))

    exata, falha = _pagina(cliente, f'"{codigo}"', historico=True)
    versoes = _quantos(exata) if exata is not None else 0
    if exata is None:
        sondas.append(Sonda("Busca exata do código, com histórico", False, falha))
    else:
        sondas.append(Sonda("Busca exata do código, com histórico", versoes > 0,
                            _contar(versoes, "versão", "versões") if versoes else "nenhum documento"))
    if exata is not None and versoes:
        tracking = next((str(r["TrackingId"]) for r in exata.registros if r.get("TrackingId")), None)
        if tracking is None:
            sondas.append(Sonda("Busca pelo Tracking ID", False, "a busca exata não trouxe o Tracking ID"))
        for sintaxe in SINTAXES_DO_TRACKING_ID if tracking else ():
            pagina, falha = _pagina(cliente, sintaxe.format(id=tracking), historico=True)
            sondas.append(_sonda_de_filtro(
                f"Busca pelo Tracking ID ({sintaxe.format(id='<id>')})", pagina, falha, total,
                lambda n: f"{_contar(n, 'versão', 'versões')} (a busca exata trouxe {versoes})"))

    pagina, falha = _pagina(cliente, BUSCA_POR_TITULO, historico=False,
                            campos=CAMPOS_DO_TITULO, page_size=PAGINA_DO_TITULO)
    sondas.append(_sonda_de_filtro(
        f"{ROTULO_TITULO} ({BUSCA_POR_TITULO})", pagina, falha, total,
        lambda n: f"{n} de {total} documentos" if total is not None else _contar(n, "documento", "documentos")))
    sondas.append(_sonda_das_listas_novas(pagina))
    return sondas


def _sonda_das_listas_novas(pagina: Pagina | None) -> Sonda:
    """Das que a busca por título trouxe, quantas são lista nova pela regra do Gestão
    PMIB. Só conta: título e código não saem no `detalhe`."""
    if pagina is None:
        return Sonda(SONDA_LISTAS_NOVAS, False, "sem a busca por título")
    # Import tardio: a regra mora no serviço do Gestão PMIB (uma implementação por
    # conceito), que puxa pandas e openpyxl; o diagnóstico só precisa dela aqui.
    from sigft.services.pmib_manager import e_lista_de_sobressalentes
    lidas = len(pagina.registros)
    novas = sum(1 for r in pagina.registros
                if e_lista_de_sobressalentes(r.get("DocumentNumber"), r.get("Title")))
    detalhe = f"{novas} de {lidas} com título de sobressalentes"
    if pagina.total is not None and pagina.total > lidas:
        detalhe += f" (só a 1ª página: {pagina.total} no total)"
    return Sonda(SONDA_LISTAS_NOVAS, novas > 0, detalhe)


def linha(sonda: Sonda) -> str:
    """A sonda numa linha, para o terminal e para o console da tela:
    `OK      Login no Aconex: token recebido`."""
    return f"{'OK' if sonda.ok else 'FALHOU':<8}{sonda.nome}: {sonda.detalhe}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sigft.core.aconex.diagnostico",
                                     description="Prova quais buscas do Aconex funcionam.")
    parser.add_argument("codigo", help="código de uma lista de sobressalentes no Aconex")
    parser.add_argument("--perfil", help="nome do perfil no cofre do DocManager")
    args = parser.parse_args(argv)

    perfis = ler_perfis()
    if not perfis:
        print(f"Nenhum perfil do Aconex legível em {caminho_do_cofre()}. "
              "Cadastre o perfil no DocManager, nesta conta do Windows.")
        return 1
    perfil = escolher_perfil(perfis, args.perfil or prefs.ler_preferencia(PREFERENCIA_PERFIL, ""))
    if perfil is None:
        print("Há mais de um perfil no cofre. Escolha com --perfil: " + ", ".join(p.nome for p in perfis))
        return 1

    for sonda in sondar(ClienteAconex(perfil, tentativas=TENTATIVAS_DO_DIAGNOSTICO), args.codigo):
        print(linha(sonda))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
