r"""
sigft/core/prefs.py — memória de últimos caminhos usados nos diálogos de
arquivo + pastas padrão configuráveis (Checkpoint 1.5 do plano de
refatoração, decisão de produto nº 7).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.5, e a decisão de
produto nº 7 na seção 0 ("Memória de caminhos nos diálogos de arquivo +
pastas padrão configuráveis"): cada diálogo de arquivo deve abrir na última
pasta usada PARA AQUELE TIPO DE ARQUIVO/CAMPO (ex.: no AutoSpec, o seletor de
ficha Excel abre na pasta do último Excel; o de manuais abre na pasta do
último PDF — sem vai-e-vem entre pastas). Além disso, pastas de trabalho
conhecidas (Box da Itaipu) vêm pré-configuradas como padrão, editáveis pela
UI num painel futuro ("Pastas padrão" na Home).

ESCOPO DESTA ETAPA (1ª metade do CP 1.5, aditiva): só os dois módulos novos
(este + `sigft/app/file_dialogs.py`) nascem aqui, testados de ponta a ponta.
A migração dos ~34 call sites de `filedialog.*` em `frontend.py` para os
wrappers de `app/file_dialogs.py`, o pré-preenchimento dos campos de pasta do
`ModuloPDM` e o painel "Pastas padrão" editável na Home (que consumiria
`get_default_dir`/`set_default_dir` abaixo) ficam para a etapa seguinte — ver
docs/refatoracao/PENDENCIAS.md. `frontend.py` NÃO é tocado neste checkpoint.

Estado persistido
------------------
`user_prefs.json` na raiz do repositório/instalação (mesmo padrão de
`api_config.json`/`sigft.config.CONFIG_FILE` — já listado em `.gitignore`,
por ser específico de usuário/máquina, não versionado). Formato:

    {
      "ultimos":       {"<chave>": "<pasta>", ...},
      "categorias":    {"<categoria>": "<pasta>", ...},
      "pastas_padrao": {"<nome>": "<pasta customizada pelo usuário>", ...}
    }

  - ``ultimos[chave]``: última pasta usada para um CAMPO específico (ex.:
    ``"autospec.manuais"``) — a camada mais granular de resolução.
  - ``categorias[categoria]``: última pasta usada para um TIPO de arquivo
    (ex.: ``"excel"``, ``"pdf"``, ``"json"``, ``"pasta"``) — faz vários
    campos distintos do mesmo tipo caírem na mesma pasta quando ainda não há
    histórico específico daquela chave.
  - ``pastas_padrao[nome]``: override do usuário para uma pasta padrão
    SEMEADA (``PASTAS_PADRAO_SEED`` abaixo) — o que um futuro painel "Pastas
    padrão" da Home gravaria via `set_default_dir` (painel em si é FORA do
    escopo desta etapa; só a API de leitura/escrita nasce aqui).

Arquivo ausente ou corrompido (JSON inválido, JSON que não é um objeto, ou
uma das 3 seções internas com tipo inesperado) -> estado vazio, SEM levantar
exceção — mesmo espírito tolerante de `sigft.config.carregar_chaves`.

`config_path` é parâmetro keyword-only em toda função pública, com default
`CONFIG_FILE` — espelha `sigft.config.carregar_chaves(config_path=CONFIG_FILE)`
— por isso testável 100% com `tmp_path`, sem tocar no `user_prefs.json` real
do repositório (nem precisar de nenhum mock).

Validação de existência (os.path.isdir)
----------------------------------------
Um caminho gravado numa sessão anterior pode não existir mais na máquina
atual (pasta do Box renomeada/movida, arquivo de prefs copiado de outra
máquina, pendrive desconectado). Por isso `get_initial_dir`/`get_default_dir`
SEMPRE validam `os.path.isdir(...)` em CADA candidato antes de devolvê-lo —
um candidato inexistente (ou de tipo inesperado, ex.: JSON adulterado à mão)
é silenciosamente PULADO, caindo para a camada seguinte da resolução. Nunca
propaga erro; nunca devolve ao chamador um caminho morto para o
`tkinter.filedialog` tentar abrir.

Só stdlib (`json`, `os`, `pathlib`) — nenhuma dependência de UI (nem
tkinter/customtkinter), nenhuma dependência pesada. Importável no ambiente de
teste sem stub nenhum (ver tests/conftest.py). Ver tests/test_prefs.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# =============================================================================
# Arquivo de estado
# =============================================================================

# Mesmo padrão de `sigft.config.CONFIG_FILE` ("api_config.json"): nome
# relativo (resolvido a partir do cwd do processo — raiz do repo/instalação),
# já listado em `.gitignore`.
CONFIG_FILE = "user_prefs.json"

# As seções do estado persistido — ver docstring do módulo.
#
# ⚠️ Seção que não estiver AQUI é descartada ao carregar, mesmo que
# `remember_*` a tenha gravado. Foi o que aconteceu com "arquivos" em
# 2026-09-03: `remember_file` gravava, `get_last_file` lia `None`, e o mural
# de atividades dizia "não encontrei o mapeamento" sem nenhum erro aparecer.
_SECOES_ESTADO = ("ultimos", "categorias", "pastas_padrao", "arquivos")


def _estado_vazio() -> dict[str, dict[str, str]]:
    """Novo estado vazio (as 3 seções, cada uma um dict vazio) — usado como
    fallback sempre que o arquivo de prefs não existe ou está corrompido (no
    todo ou em parte)."""
    return {secao: {} for secao in _SECOES_ESTADO}


def _carregar_estado(config_path: str | os.PathLike[str]) -> dict[str, dict[str, str]]:
    """Lê `config_path`, tolerante a ausência/corrupção (mesmo espírito de
    `sigft.config.carregar_chaves`): arquivo ausente, JSON inválido, JSON
    válido mas que não é um objeto, ou uma das 3 seções com tipo diferente de
    dict -> aquela seção (ou o estado inteiro) cai para vazio, NUNCA levanta
    exceção.

    Normaliza SEMPRE as 3 chaves (`ultimos`/`categorias`/`pastas_padrao`) no
    dict devolvido, mesmo que o arquivo real só tenha algumas — quem chama
    nunca precisa checar `.get(secao, {})`.
    """
    estado = _estado_vazio()

    if not os.path.exists(config_path):
        return estado

    try:
        with open(config_path, "r", encoding="utf-8") as arquivo:
            bruto = json.load(arquivo)
    except Exception:
        return estado

    if not isinstance(bruto, dict):
        return estado

    for secao in _SECOES_ESTADO:
        valor = bruto.get(secao)
        if isinstance(valor, dict):
            estado[secao] = valor
    return estado


def _salvar_estado(estado: dict[str, dict[str, str]], config_path: str | os.PathLike[str]) -> None:
    """Grava `estado` em `config_path` como JSON (UTF-8, indentado — arquivo
    pensado para ser legível/editável à mão se necessário)."""
    with open(config_path, "w", encoding="utf-8") as arquivo:
        json.dump(estado, arquivo, ensure_ascii=False, indent=2, sort_keys=True)


def _pasta_valida(candidato: object) -> str | None:
    """Devolve `candidato` se for uma string não-vazia apontando para uma
    pasta que existe DE FATO no disco agora; senão `None`. Único ponto de
    validação usado por toda a resolução (`ultimos`, `categorias`,
    `pastas_padrao`, `PASTAS_PADRAO_SEED`) — um valor de tipo inesperado
    (JSON adulterado à mão) ou um caminho que não existe mais é tratado como
    "candidato ausente", nunca propaga erro (`os.path.isdir` de um tipo
    não-string poderia levantar `TypeError`; o `isinstance` abaixo evita
    isso)."""
    if isinstance(candidato, str) and candidato and os.path.isdir(candidato):
        return candidato
    return None


# =============================================================================
# Pastas padrão SEMEADAS (decisão de produto nº 7)
# =============================================================================
# Relativas a `Path.home()` -- funcionam em qualquer máquina com o Box da
# Itaipu sincronizado no perfil do usuário (Windows ou não), sem hardcodar
# letra de unidade/usuário. Nomes de subpasta copiados LITERALMENTE do texto
# da decisão nº 7 (PLANO_REFATORACAO.md, seção 0, item 7) e do próprio CP 1.5.

BASE_BOX = Path.home() / "Box" / "CMI - Consórcio Itaipu" / "11 - Ger. Engenharia" / "15 - PDM"

# nome lógico -> Path semeado. "Só são usadas se existirem no disco" (decisão
# nº 7 / CP 1.5) — a validação de existência acontece em `get_default_dir`
# (via `_pasta_valida`), não aqui: este dict é só a TABELA de candidatos.
PASTAS_PADRAO_SEED: dict[str, Path] = {
    "sobressalentes_pmib": BASE_BOX / "SOBRESSALENTES - PMIB",  # fichas/STATUS
    "pdms_modificados": BASE_BOX / "PDMs modificados",
    "templates_ficha": BASE_BOX / "Templates",  # template da ficha
}

# chave de campo ("<modulo>.<campo>", dot-separated minúsculo) -> nome lógico
# de `PASTAS_PADRAO_SEED`, usado no passo 3 de `get_initial_dir`. Populado
# com as 3 chaves que a etapa SEGUINTE (migração de `frontend.ModuloPDM`) vai
# usar — nomes de campo ilustrativos (mas já alinhados aos atributos reais de
# `frontend.ModuloPDM`: `caminho_destino`, `path_template`/`_sel_template`,
# `path_status_pmib`/`_sel_status_pmib`), ajustáveis por aquela etapa se
# necessário (ver docs/refatoracao/PENDENCIAS.md).
PASTAS_PADRAO_POR_CHAVE: dict[str, str] = {
    "pdm.caminho_destino": "pdms_modificados",
    "pdm.template": "templates_ficha",
    "pdm.status_pmib": "sobressalentes_pmib",
}


# =============================================================================
# API pública
# =============================================================================

def get_initial_dir(
    chave: str,
    categoria: str,
    *,
    config_path: str | os.PathLike[str] = CONFIG_FILE,
) -> str | None:
    """Resolve o diretório inicial para abrir um diálogo de arquivo, nesta
    ordem (a PRIMEIRA camada com um candidato que exista de fato no disco
    vence):

      1. Última pasta usada para essa `chave` específica (ex.:
         ``"autospec.manuais"``).
      2. Última pasta usada para essa `categoria` (ex.: ``"pdf"``).
      3. Pasta padrão mapeada para essa `chave` via `PASTAS_PADRAO_POR_CHAVE`
         (override do usuário se houver, senão a semeada — delega para
         `get_default_dir`, que já valida as duas camadas).
      4. `None` — comportamento atual do sistema: o `tkinter.filedialog`
         abre onde quiser (sem `initialdir`).

    Cada candidato passa por `_pasta_valida` (`os.path.isdir`); um candidato
    que não existe mais é PULADO, nunca propagado — ver docstring do módulo.
    """
    estado = _carregar_estado(config_path)

    candidato = _pasta_valida(estado["ultimos"].get(chave))
    if candidato is not None:
        return candidato

    candidato = _pasta_valida(estado["categorias"].get(categoria))
    if candidato is not None:
        return candidato

    nome_padrao = PASTAS_PADRAO_POR_CHAVE.get(chave)
    if nome_padrao is not None:
        candidato = get_default_dir(nome_padrao, config_path=config_path)
        if candidato is not None:
            return candidato

    return None


def remember_dir(
    chave: str,
    categoria: str,
    caminho: str | os.PathLike[str],
    *,
    config_path: str | os.PathLike[str] = CONFIG_FILE,
) -> None:
    """Grava `caminho` como a última pasta usada tanto para `chave` quanto
    para `categoria` (as DUAS, na mesma chamada), persistindo em
    `config_path`.

    `caminho` deve ser uma PASTA, não um arquivo: se quem chama tiver um
    caminho de ARQUIVO (o caso comum — resultado de
    `askopenfilename`/`asksaveasfilename`), resolver para a pasta-mãe
    (`os.path.dirname`) é responsabilidade de `sigft.app.file_dialogs`, NÃO
    desta função.
    """
    estado = _carregar_estado(config_path)
    caminho_str = os.fspath(caminho)
    estado["ultimos"][chave] = caminho_str
    estado["categorias"][categoria] = caminho_str
    _salvar_estado(estado, config_path)


def get_default_dir(
    nome: str,
    *,
    config_path: str | os.PathLike[str] = CONFIG_FILE,
) -> str | None:
    """Devolve a pasta padrão de nome lógico `nome` (ex.:
    ``"pdms_modificados"``), nesta ordem:

      1. Override salvo pelo usuário (`pastas_padrao[nome]` — gravado via
         `set_default_dir`, tipicamente pelo futuro painel "Pastas padrão" da
         Home), SE existir de fato no disco.
      2. Pasta padrão SEMEADA (`PASTAS_PADRAO_SEED[nome]`), SE existir de
         fato no disco.
      3. `None`, se nenhuma das duas existir (ou `nome` for desconhecido de
         `PASTAS_PADRAO_SEED` e não houver override salvo).
    """
    estado = _carregar_estado(config_path)

    candidato = _pasta_valida(estado["pastas_padrao"].get(nome))
    if candidato is not None:
        return candidato

    seed = PASTAS_PADRAO_SEED.get(nome)
    if seed is not None:
        candidato = _pasta_valida(str(seed))
        if candidato is not None:
            return candidato

    return None


def set_default_dir(
    nome: str,
    caminho: str | os.PathLike[str],
    *,
    config_path: str | os.PathLike[str] = CONFIG_FILE,
) -> None:
    """Grava `caminho` como override do usuário para a pasta padrão de nome
    lógico `nome`, persistindo em `config_path`.

    Não valida `os.path.isdir` na GRAVAÇÃO (a validação acontece só na
    LEITURA, em `get_default_dir`/`_pasta_valida`) — permite salvar um
    caminho e o usuário criar a pasta depois, sem precisar salvar de novo.
    """
    estado = _carregar_estado(config_path)
    estado["pastas_padrao"][nome] = os.fspath(caminho)
    _salvar_estado(estado, config_path)


# =============================================================================
# Lembrar um ARQUIVO inteiro  [2026-09-03]
# =============================================================================
# `remember_dir` guarda a PASTA de onde o usuário escolheu um arquivo — é o que
# o CP 1.5 precisava, porque o objetivo era abrir o diálogo no lugar certo.
#
# Mas o mural de atividades precisa do ARQUIVO: ele lê a planilha de mapeamento
# sem passar por diálogo nenhum. Sem isto, o mural nunca achava o arquivo e
# dizia "não encontrei o mapeamento" mesmo com o usuário tendo acabado de
# rodar o PMIB Manager sobre ele — foi o que aconteceu em 2026-09-03.
CHAVE_ARQUIVOS = "arquivos"

# A planilha de mapeamento que o PMIB Manager usa. O mural de atividades
# da Home lê por esta chave -- é o que liga as duas telas sem que a Home
# precise pedir o arquivo de novo.
CHAVE_MAPEAMENTO = "pmib_manager.mapeamento"


def remember_file(
    chave: str,
    caminho: str | os.PathLike[str],
    *,
    config_path: str | os.PathLike[str] = CONFIG_FILE,
) -> None:
    """Guarda o CAMINHO COMPLETO de um arquivo sob `chave`.

    Não valida se o arquivo existe: o momento de gravar é quando o usuário
    acabou de escolhê-lo, e a validação certa é na LEITURA (`get_last_file`),
    porque o arquivo pode sumir entre uma coisa e outra.
    """
    if not caminho:
        return
    estado = _carregar_estado(config_path)
    estado.setdefault(CHAVE_ARQUIVOS, {})[chave] = str(caminho)
    _salvar_estado(estado, config_path)


def get_last_file(
    chave: str,
    *,
    config_path: str | os.PathLike[str] = CONFIG_FILE,
) -> str | None:
    """O último arquivo lembrado sob `chave`, SE ainda existir no disco.

    Devolve `None` quando não há registro ou quando o arquivo sumiu — quem
    chama trata os dois casos igual, que é o certo: nos dois não há o que ler.
    """
    estado = _carregar_estado(config_path)
    caminho = estado.get(CHAVE_ARQUIVOS, {}).get(chave)
    if caminho and os.path.isfile(caminho):
        return caminho
    return None
