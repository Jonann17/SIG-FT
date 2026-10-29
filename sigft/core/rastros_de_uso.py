"""O que, na pasta de dados, diz que alguém já usou o SIG-FT (2026-10-28).

Uma regra, dois donos de pergunta: a boas-vindas (`sigft/app/boas_vindas.py`:
só para quem nunca usou) e a janela de novidades (`core/novidades.py`: o
`user_prefs.json` sem versão gravada é atualização só se houver uso -- a
pergunta do idioma grava o arquivo na primeira abertura, e o changelog abria
por cima da boas-vindas de quem acabou de instalar). Mora no `core` porque o
`core` não importa o `app`; não importa Qt.

O que é rastro de uso (`rastros_de_uso`)
----------------------------------------
O que só existe porque alguém TRABALHOU num módulo:

* `user_prefs.json` com qualquer entrada nas seções de caminho e de tabela
  (`SECOES_DE_USO`): a última pasta ou arquivo de um diálogo, as pastas padrão,
  os recentes, as colunas de uma tabela. Todo módulo abre um diálogo de
  arquivo, e o diálogo grava a pasta: é o rastro mais certo. Quem atualiza de
  uma versão anterior à pasta de dados traz o arquivo pela migração
  (`dados_usuario.migrar_se_preciso`, antes da janela), com as pastas dentro;
* `user_prefs.json` com a versão vista das novidades DIFERENTE da atual: a janela
  de novidades só grava no app instalado e só depois desta decisão
  (`novidades.agendar_na_abertura`, no fim da montagem); achar uma versão
  anterior gravada é de quem abriu uma versão velha e atualizou, mesmo sem nunca
  ter aberto um diálogo de arquivo. A MESMA versão não conta: foi esta
  instalação que abriu antes, e saiu sem escolher (vê de novo);
* `user_prefs.json` que existe e não se lê: alguém o gravou; e mostrar sem
  conseguir gravar a vista seria mostrar em toda abertura;
* `logs/` com algum arquivo que não seja dos que a própria abertura grava
  (`LOGS_DA_ABERTURA`): o log de execução de um módulo
  (`duplicadas_2026-08-18_14-32-05.log`), ou uma subpasta com arquivo (o resumo
  do lote, o diagnóstico do AMP);
* `api_config.json` com alguma chave preenchida.

O que NÃO é (a primeira abertura grava antes de a janela decidir, ou logo
depois): o idioma, o tema, a letra, o nome e o "já perguntou", a versão vista
das novidades quando é a atual, as opções liga/desliga (o menu recolhido), o `sigft.log` e o
diário. Contar qualquer um deles faria a página nunca aparecer para quem
acabou de instalar.

Levanta `OSError` se a pasta não se lê: cada dono da pergunta decide o que a
dúvida vale.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# As seções do `user_prefs.json` que só se enchem trabalhando num módulo.
SECOES_DE_USO = ("ultimos", "categorias", "pastas_padrao", "arquivos", "recentes", "colunas")

# O que a própria abertura grava em `logs/` (o `sigft.log` do `.exe` sem console e
# o diário de quedas): começa com um destes nomes, não é uso.
LOGS_DA_ABERTURA = ("sigft.log", "diario.", "queda.log")

ARQUIVO_DE_CHAVES = "api_config.json"


def _pasta_de_dados() -> Path:
    from sigft.core.dados_usuario import pasta_dados

    return pasta_dados()


def _ler_json(arquivo: Path):
    """`(existe, conteúdo)`; conteúdo `None` quando o arquivo não se lê."""
    if not arquivo.is_file():
        return False, None
    try:
        return True, json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True, None


def _rastros_nas_preferencias(pasta: Path) -> list[str]:
    from sigft.core.prefs import CHAVE_NOVIDADES, CONFIG_FILE

    existe, dados = _ler_json(pasta / CONFIG_FILE)
    if not existe:
        return []
    if not isinstance(dados, dict):
        return [f"{CONFIG_FILE} (ilegível)"]
    rastros = [f"{CONFIG_FILE}:{secao}" for secao in SECOES_DE_USO if dados.get(secao)]
    novidades = dados.get(CHAVE_NOVIDADES)
    vista = novidades.get("ultima_versao_vista") if isinstance(novidades, dict) else None
    if isinstance(vista, str) and vista and vista != _versao_atual():
        rastros.append(f"{CONFIG_FILE}:novidades ({vista})")
    return rastros


def _versao_atual() -> str:
    from sigft import _build_info

    return _build_info.VERSAO


def _arquivo_da_abertura(nome: str) -> bool:
    return nome.startswith(LOGS_DA_ABERTURA)


def _tem_arquivo(pasta: Path) -> bool:
    return any(os.path.isfile(os.path.join(raiz, nome))
               for raiz, _dirs, nomes in os.walk(pasta) for nome in nomes)


def _rastros_nos_logs(pasta: Path) -> list[str]:
    logs = pasta / "logs"
    if not logs.is_dir():
        return []
    rastros = []
    for item in sorted(logs.iterdir()):
        if item.is_dir():
            if _tem_arquivo(item):
                rastros.append(f"logs/{item.name}")
        elif not _arquivo_da_abertura(item.name):
            rastros.append(f"logs/{item.name}")
    return rastros


def _rastros_nas_chaves(pasta: Path) -> list[str]:
    _existe, dados = _ler_json(pasta / ARQUIVO_DE_CHAVES)
    if isinstance(dados, dict) and any(isinstance(v, str) and v.strip() for v in dados.values()):
        return [ARQUIVO_DE_CHAVES]
    return []


def rastros_de_uso(pasta: str | os.PathLike[str] | None = None) -> list[str]:
    """O que, na pasta de dados, diz que alguém já usou o SIG-FT (lista vazia:
    ninguém). Ver o docstring do módulo. Levanta `OSError` se a pasta não se lê;
    quem chama trata."""
    raiz = Path(pasta) if pasta is not None else _pasta_de_dados()
    return [*_rastros_nas_preferencias(raiz), *_rastros_nos_logs(raiz), *_rastros_nas_chaves(raiz)]
