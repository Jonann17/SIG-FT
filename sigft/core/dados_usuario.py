"""Onde ficam os arquivos que são do USUÁRIO, e não do programa.

O problema que este módulo resolve
----------------------------------
Até a v1.0.0 o SIG-FT resolvia `api_config.json`, `user_prefs.json`, os caches
de modelo e a pasta `logs/` a partir do **diretório de trabalho** — ou seja, da
pasta do programa. Funcionava porque o app era extraído em `%LOCALAPPDATA%`,
onde o usuário escreve.

Com o instalador, o padrão passa a ser **`Program Files`**, e ali usuário comum
não escreve. Os quatro deixariam de funcionar de uma vez, e o sintoma seria o
pior possível: as chaves de API sumindo a cada abertura — e a pasta `logs/`,
que é justamente o que diria o motivo, também sem gravar.

Há um segundo motivo, independente do instalador: **a atualização reescreve a
pasta do programa.** Dado do usuário guardado lá seria apagado a cada versão.

Por isso tudo isso muda para `Documentos\\SIG-FT\\`, **fora da pasta do
programa**.

O que este módulo NÃO faz
-------------------------
Não cifra nada. Decisão do usuário em 2026-09-18: as chaves de API continuam
**compartilháveis** entre as pessoas do time, como já eram. O que muda é o
LUGAR, não o sigilo — o objetivo aqui é a atualização não encostar nelas.

Cifrar com a DPAPI do Windows (como o DocManager faz) derivaria a chave da
conta do Windows, e o arquivo deixaria de servir para outra pessoa — que é
exatamente o contrário do que foi pedido. Se um dia a decisão mudar, o ponto
de entrada é este módulo, e só ele.

⚠️ Consequência que continua valendo: as chaves ficam em texto claro em
`Documentos\\SIG-FT\\api_config.json`. Se alguém sair do time ou o arquivo
vazar, a saída é **rotacionar as chaves no provedor**.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

NOME_DA_PASTA = "SIG-FT"

# A variável existe primeiro para os TESTES. Sem ela, a suíte escreveria na
# pasta Documentos DE VERDADE de quem a rodasse, e o arquivo deixado lá
# passaria a valer para o app da pessoa. O DocManager pagou exatamente isso com
# o token de atualização. Serve também para quem quiser apontar os dados para
# outro lugar (uma pasta de rede, por exemplo).
ENV_PASTA = "SIGFT_DADOS_DIR"

_pasta_resolvida: Path | None = None


def esquecer_pasta() -> None:
    """Descarta o caminho já resolvido — usado pelos testes entre um e outro."""
    global _pasta_resolvida
    _pasta_resolvida = None


def _documentos() -> Path:
    """A pasta Documentos do usuário, com queda para a raiz do perfil.

    No Windows o nome é localizado ("Documentos" em português, "Documents" em
    inglês) e a pasta pode ter sido redirecionada para o OneDrive. Tentar os
    dois nomes cobre o caso comum sem depender de API do shell; se nenhum
    existir, a raiz do perfil serve — é gravável, que é o requisito.
    """
    lar = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
    for nome in ("Documents", "Documentos"):
        if (lar / nome).is_dir():
            return lar / nome
    return lar


def pasta_dados() -> Path:
    """`Documentos\\SIG-FT\\` (ou o que `SIGFT_DADOS_DIR` disser). Cria se faltar.

    Nunca devolve o diretório de trabalho: é justamente o que não funciona sob
    `Program Files`.
    """
    global _pasta_resolvida
    if _pasta_resolvida is not None:
        return _pasta_resolvida

    if (escolhido := os.environ.get(ENV_PASTA, "").strip()):
        destino = Path(escolhido)
    else:
        destino = _documentos() / NOME_DA_PASTA

    try:
        destino.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Disco cheio, pasta sem permissão, caminho inválido. Não dá para
        # parar o app por isso: quem grava trata o próprio erro.
        pass

    _pasta_resolvida = destino
    return destino


def caminho(nome: str) -> Path:
    """Caminho completo de um arquivo de dados do usuário."""
    return pasta_dados() / nome


def e_nome_puro(texto: str) -> bool:
    """`True` se `texto` é um NOME de arquivo, sem nenhuma pasta.

    Checa as DUAS barras de propósito, em vez de usar `os.path.dirname`: no
    POSIX, o `dirname` de `C:\\x\\api_config.json` é `""`, e um caminho do
    Windows passaria por nome puro num teste rodando em Linux. Esta base já
    pagou duas vezes por tratamento de caminho que muda com o sistema — ver
    `tests/_caminhos.py`.
    """
    return "/" not in texto and "\\" not in texto


def resolver_config(config_path, nome_padrao: str):
    """Para onde um `config_path` aponta DE VERDADE. Três casos:

    * `None` -> `nome_padrao` na pasta de dados;
    * **NOME puro** (`"api_config.json"`) -> o mesmo, na pasta de dados. As
      constantes `CONFIG_FILE` são o NOME do arquivo, não um caminho: quem as
      passa quer O arquivo, não um arquivo relativo à pasta em que o app por
      acaso foi aberto;
    * caminho com pasta -> **intocado**. É a costura que os testes usam
      (`tmp_path`), e o conserto não pode atropelá-la.

    O caso do meio nasceu na primeira instalação real (2026-09-21) e derrubou
    o aplicativo inteiro. `file_dialogs` e `core/llm/selecao.py` passavam a
    constante crua como default, o que **anulava** a resolução tardia:
    `open("user_prefs.json", "w")` grava relativo ao diretório de trabalho, que
    no app instalado é `Program Files`, onde usuário comum não escreve. O
    `PermissionError` subia pelo callback do Tk e sumia no stderr (o
    `.exe` é `console=False`) — então escolher um arquivo "não fazia nada", em
    TODOS os módulos.

    A regra mora aqui, e não nas assinaturas, porque havia 13 pontos com o
    nome cru e um deles é de outra frente: consertar o resolvedor conserta
    todos, inclusive os que não posso editar.
    """
    if config_path is None:
        return str(caminho(nome_padrao))
    if e_nome_puro(os.fspath(config_path)):
        return str(caminho(os.fspath(config_path)))
    return config_path


def pasta_logs() -> Path:
    """`Documentos\\SIG-FT\\logs\\`. Cria se faltar.

    Era `logs/` ao lado do `.exe`, que sob `Program Files` não grava — e o log
    é o pior lugar para falhar em silêncio, porque é ele que explicaria
    qualquer outra falha.
    """
    destino = pasta_dados() / "logs"
    try:
        destino.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return destino


# ───────────────── importação do lugar antigo (uma vez só) ──────────────────

# Quais chaves do `.env` correspondem a quais campos do `api_config.json`.
# É o mesmo mapa de `config.ENV_VAR_POR_CHAVE`, mas invertido e local: este
# módulo não importa `config` de propósito, para poder ser usado no bootstrap
# do app antes de qualquer coisa pesada subir.
_ENV_PARA_CHAVE = {
    "API_GEMINI_LUAN_GMAIL": "GEMINI",
    "GOOGLE_SEARCH_API": "GOOGLE_SEARCH",
    "GOOGLE_CSE_API": "GOOGLE_CSE",
    "LLAMA_CLOUD_API": "LLAMA_CLOUD",
    "OPENROUTER_API_KEY": "OPENROUTER",
}

_ARQUIVOS_A_IMPORTAR = ("api_config.json", "user_prefs.json")

_LINHA_ENV = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def _ler_env(arquivo: Path) -> dict[str, str]:
    """As chaves de API de um `.env`, no formato do `api_config.json`.

    Análise mínima de propósito: `NOME=valor`, ignorando comentário e linha
    vazia, com aspas removidas. Não é um interpretador de `.env` — é a leitura
    única da migração, e quem tem `.env` tem um arquivo de cinco linhas.
    """
    achadas: dict[str, str] = {}
    try:
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return achadas

    for linha in texto.splitlines():
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        if not (m := _LINHA_ENV.match(linha)):
            continue
        nome, valor = m.group(1), m.group(2).strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        if (chave := _ENV_PARA_CHAVE.get(nome)) and valor:
            achadas[chave] = valor
    return achadas


def importar_do_lugar_antigo(pasta_antiga: str | os.PathLike[str]) -> list[str]:
    """Traz `api_config.json`, `user_prefs.json` e o `.env` da pasta do programa.

    Devolve os nomes do que foi importado (lista vazia quando não havia nada a
    trazer, que é o caso normal a partir da segunda abertura).

    **Nunca sobrescreve** o que já está no lugar novo: rodar de novo não pode
    desfazer o que a pessoa cadastrou depois pela tela do app.

    Nunca levanta exceção. Um JSON corrompido na pasta antiga não pode impedir
    o app de abrir — perder a importação é ruim, não abrir é pior.
    """
    origem = Path(pasta_antiga)
    importados: list[str] = []

    if not origem.is_dir():
        return importados

    for nome in _ARQUIVOS_A_IMPORTAR:
        destino = caminho(nome)
        if destino.exists():
            continue
        antigo = origem / nome
        if not antigo.is_file():
            continue
        try:
            dados = json.loads(antigo.read_text(encoding="utf-8"))
            if not isinstance(dados, dict):
                continue
            destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                               encoding="utf-8")
            importados.append(nome)
        except (OSError, ValueError):
            # JSON quebrado ou arquivo ilegível: segue sem ele.
            continue

    # O `.env` só entra quando não houve `api_config.json` para importar: o
    # JSON é o que a tela do app grava, então é o mais recente dos dois.
    destino = caminho("api_config.json")
    if not destino.exists() and (antigo_env := origem / ".env").is_file():
        if (chaves := _ler_env(antigo_env)):
            try:
                destino.write_text(json.dumps(chaves, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
                importados.append(".env")
            except OSError:
                pass

    return importados


def _pasta_do_programa() -> Path:
    """Onde o `.exe` (ou o repositório) está — o lugar ANTIGO dos dados.

    No executável do PyInstaller é a pasta do `.exe`; rodando do `.py`, a raiz
    do repositório. É de lá que a migração traz `api_config.json`,
    `user_prefs.json` e o `.env` de quem já usava o SIG-FT.
    """
    import sys

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def migrar_se_preciso(pasta_antiga: str | os.PathLike[str] | None = None) -> list[str]:
    """Traz os dados do lugar antigo, uma vez. Chamada na abertura do app.

    Devolve o que foi importado — lista vazia no caso normal, que é a segunda
    abertura em diante. Silenciosa quando não há nada a fazer: um aviso que
    aparece toda vez deixa de ser lido.

    **Nunca levanta.** Perder a importação é ruim; não abrir é pior — o usuário
    recadastra as chaves pela tela da Home, mas um app que não sobe não tem
    tela. Por isso o `except` largo aqui é deliberado, e não descuido.
    """
    try:
        origem = Path(pasta_antiga) if pasta_antiga is not None else _pasta_do_programa()
        return importar_do_lugar_antigo(origem)
    except Exception:  # noqa: BLE001 — ver o docstring: a abertura vem antes
        return []
