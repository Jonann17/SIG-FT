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
`Tk.filedialog` tentar abrir.

Só stdlib (`json`, `os`, `pathlib`) — nenhuma dependência de UI (nem
Tk/interface antiga), nenhuma dependência pesada. Importável no ambiente de
teste sem stub nenhum (ver tests/conftest.py). Ver tests/test_prefs.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# =============================================================================
# Arquivo de estado
# =============================================================================

# Mesmo padrão de `sigft.config.CONFIG_FILE` ("api_config.json"): o NOME do
# arquivo, que é o default do parâmetro `config_path` (os testes o
# sobrescrevem com `tmp_path`). Quem quer o caminho real chama
# `caminho_config()` logo abaixo.
CONFIG_FILE = "user_prefs.json"


def caminho_config() -> str:
    """Onde o `user_prefs.json` mora DE VERDADE: `Documentos\\SIG-FT\\`.

    Mesmo motivo de `config.caminho_config()`: sob `Program Files` o
    diretório de trabalho é somente-leitura, e a atualização reescreveria a
    pasta do programa. As preferências (últimas pastas usadas nos diálogos)
    são do usuário e sobrevivem à atualização.
    """
    from sigft.core.dados_usuario import caminho

    return str(caminho(CONFIG_FILE))


def _resolver(config_path):
    """Para onde o `user_prefs.json` vai DE VERDADE.

    A regra (e o defeito que a originou) mora em
    `dados_usuario.resolver_config`, que é o dono único dela — `prefs` e
    `core/llm/selecao.py` tinham a mesma pergunta a responder, e duas cópias
    divergem na primeira pressa.

    A resolução continua TARDIA. Se o default das funções abaixo fosse
    `caminho_config()`, ele seria avaliado no import do módulo — e a pasta de
    dados ficaria congelada antes de `SIGFT_DADOS_DIR` poder apontá-la, que é
    como os testes (e quem quiser outra pasta) a redirecionam.
    """
    from sigft.core.dados_usuario import resolver_config

    return resolver_config(config_path, CONFIG_FILE)


# As seções do estado persistido — ver docstring do módulo.
#
# ⚠️ Seção que não estiver AQUI é descartada ao carregar, mesmo que
# `remember_*` a tenha gravado. Foi o que aconteceu com "arquivos" em
# 2026-09-03: `remember_file` gravava, `get_last_file` lia `None`, e o mural
# de atividades dizia "não encontrei o mapeamento" sem nenhum erro aparecer.
_SECOES_ESTADO = ("ultimos", "categorias", "pastas_padrao", "arquivos", "opcoes", "novidades",
                  "preferencias", "recentes", "colunas")


def _estado_vazio() -> dict[str, dict[str, str]]:
    """Novo estado vazio (as seções de `_SECOES_ESTADO`, cada uma um dict vazio) — usado como
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
    config_path = _resolver(config_path)
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
    config_path = _resolver(config_path)
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
    "templates_ficha": BASE_BOX / "Templates",  # template da ficha
}

# chave de campo ("<modulo>.<campo>", dot-separated minúsculo) -> nome lógico
# de `PASTAS_PADRAO_SEED`, usado no passo 3 de `get_initial_dir`: os
# seletores do template e do `_STATUS_PMIB` da tela Planilhas PMIB. [2026-10-21]
# Saiu a terceira, `pdm.caminho_destino` -> "pdms_modificados", com a pasta de
# PDMs Modificados.
PASTAS_PADRAO_POR_CHAVE: dict[str, str] = {
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
    config_path: str | os.PathLike[str] | None = None,
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
      4. `None` — comportamento atual do sistema: o `Tk.filedialog`
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


def ultima_pasta(
    chave: str,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> str | None:
    """A última pasta escolhida para `chave`, SE ainda existir: só a camada 1 de
    `get_initial_dir`, sem cair na da categoria nem na padrão.

    Serve à tela que PREENCHE um campo com a escolha de outra tela (a Conferência
    de Revisões começa na pasta raiz do Gestão PMIB): ali, a pasta de outra coisa
    não seria um ponto de partida, seria um erro.
    """
    return _pasta_valida(_carregar_estado(config_path)["ultimos"].get(chave))


def remember_dir(
    chave: str,
    categoria: str,
    caminho: str | os.PathLike[str],
    *,
    config_path: str | os.PathLike[str] | None = None,
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
    config_path: str | os.PathLike[str] | None = None,
) -> str | None:
    """Devolve a pasta padrão de nome lógico `nome` (ex.:
    ``"templates_ficha"``), nesta ordem:

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
    config_path: str | os.PathLike[str] | None = None,
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
    config_path: str | os.PathLike[str] | None = None,
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
    config_path: str | os.PathLike[str] | None = None,
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


# =============================================================================
# Opções liga/desliga  [2026-10-05]
# =============================================================================
# Uma caixa de marcar que a tela lembra entre uma abertura e outra -- a
# primeira é "Gerar painel ao terminar" do Gestão PMIB (T7 do roteiro). Mesma
# tolerância do resto do arquivo: valor que não for booleano (arquivo editado
# à mão, corrompido) vale como "nunca gravado".
CHAVE_OPCOES = "opcoes"


def get_opcao(
    chave: str,
    padrao: bool,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> bool:
    """A opção lembrada sob `chave`, ou `padrao` se nunca foi gravada."""
    valor = _carregar_estado(config_path).get(CHAVE_OPCOES, {}).get(chave)
    return valor if isinstance(valor, bool) else padrao


def set_opcao(
    chave: str,
    valor: bool,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> None:
    """Guarda a opção `chave` (liga/desliga)."""
    estado = _carregar_estado(config_path)
    estado.setdefault(CHAVE_OPCOES, {})[chave] = bool(valor)
    _salvar_estado(estado, config_path)


# =============================================================================
# Preferências de texto  [2026-10-20]
# =============================================================================
# Uma escolha com mais de dois valores, que `get_opcao` (só booleano) não
# guarda. A primeira é o tema da interface ("escuro", "claro" ou "sistema",
# `sigft/app_qt/tema.py`). Mesma tolerância: valor que não for texto não vazio
# vale como "nunca gravado"; validar o VALOR (se é um tema que existe) é de
# quem lê.
CHAVE_PREFERENCIAS = "preferencias"


def ler_preferencia(
    chave: str,
    padrao: str,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> str:
    """A preferência guardada sob `chave`, ou `padrao` se nunca foi gravada."""
    valor = _carregar_estado(config_path).get(CHAVE_PREFERENCIAS, {}).get(chave)
    return valor if isinstance(valor, str) and valor else padrao


def gravar_preferencia(
    chave: str,
    valor: str,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> None:
    """Guarda a preferência `chave` (texto)."""
    estado = _carregar_estado(config_path)
    estado.setdefault(CHAVE_PREFERENCIAS, {})[chave] = str(valor)
    _salvar_estado(estado, config_path)


# =============================================================================
# Últimos arquivos de cada diálogo  [2026-10-21]
# =============================================================================
# O menu "Últimos arquivos" ao lado do botão que abre o diálogo (etapa 1b do
# sistema visual): até `LIMITE_RECENTES` caminhos COMPLETOS por chave de
# diálogo, o mais novo primeiro. Mesma lição do "arquivos" de 2026-09-03: a seção
# está em `_SECOES_ESTADO`, senão some ao carregar. Mesma tolerância do resto:
# lista adulterada à mão (não lista, item que não é texto) vale como vazia, nunca
# levanta. Arquivo que sumiu do disco não aparece no menu, mas o caminho fica
# gravado: pode ser um Box que ainda não sincronizou.
CHAVE_RECENTES = "recentes"
LIMITE_RECENTES = 5


def _lista_de_caminhos(valor: object) -> list[str]:
    """Os textos não vazios de `valor`, se for lista; senão, lista vazia."""
    if not isinstance(valor, list):
        return []
    return [c for c in valor if isinstance(c, str) and c]


def lembrar_recente(
    chave: str,
    caminho: str | os.PathLike[str],
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> None:
    """Põe `caminho` no topo dos recentes de `chave` (sem repetir)."""
    if not caminho:
        return
    caminho = os.fspath(caminho)
    estado = _carregar_estado(config_path)
    secao = estado.setdefault(CHAVE_RECENTES, {})
    anteriores = _lista_de_caminhos(secao.get(chave))
    lista = [caminho] + [c for c in anteriores if os.path.normcase(c) != os.path.normcase(caminho)]
    secao[chave] = lista[:LIMITE_RECENTES]
    _salvar_estado(estado, config_path)


def recentes(
    chave: str,
    *,
    conferir_disco: bool = True,
    config_path: str | os.PathLike[str] | None = None,
) -> list[str]:
    """Os recentes de `chave` que ainda existem no disco, o mais novo primeiro.

    `conferir_disco=False` devolve os gravados sem olhar o disco: é para quem só
    quer saber SE há recente na montagem da tela, onde um caminho de rede fora
    do ar travaria a interface."""
    valor = _carregar_estado(config_path).get(CHAVE_RECENTES, {}).get(chave)
    lista = _lista_de_caminhos(valor)
    return [c for c in lista if os.path.isfile(c)] if conferir_disco else lista


# =============================================================================
# Última versão do app que a pessoa já viu  [2026-10-19]
# =============================================================================
# A janela de novidades (`core/novidades.para_mostrar_na_abertura`) aparece
# uma vez por versão nova: ela compara a versão do build com a guardada aqui.
# Valor que não for texto (arquivo editado à mão) vale como "nunca gravado".
CHAVE_NOVIDADES = "novidades"


def get_ultima_versao_vista(
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> str | None:
    """A última versão cujas novidades a pessoa já viu, ou `None`."""
    valor = _carregar_estado(config_path).get(CHAVE_NOVIDADES, {}).get("ultima_versao_vista")
    return valor if isinstance(valor, str) and valor else None


def set_ultima_versao_vista(
    versao: str,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> None:
    """Guarda `versao` como vista (a janela de novidades não repete)."""
    estado = _carregar_estado(config_path)
    estado.setdefault(CHAVE_NOVIDADES, {})["ultima_versao_vista"] = str(versao)
    _salvar_estado(estado, config_path)


def situacao_versao_vista(
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> tuple[str, str | None]:
    """O que se sabe da última versão vista, para a janela de novidades.

    Devolve `(situacao, versao)`:

    * `("sem_arquivo", None)` -- não há `user_prefs.json`: primeira instalação;
    * `("ilegivel", None)` -- o arquivo existe mas não se lê (JSON inválido,
      não é objeto, ou a seção/valor com tipo errado);
    * `("sem_registro", None)` -- arquivo bom, sem versão gravada: quem usava
      uma versão anterior à janela de novidades (é ATUALIZAÇÃO);
    * `("vista", "<versao>")`.

    `_carregar_estado` não serve aqui: ele devolve o mesmo estado vazio para
    "sem arquivo" e "corrompido", e é justamente essa diferença que importa.
    """
    caminho = _resolver(config_path)
    if not os.path.exists(caminho):
        return "sem_arquivo", None
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            bruto = json.load(arquivo)
    except Exception:
        return "ilegivel", None
    if not isinstance(bruto, dict):
        return "ilegivel", None
    secao = bruto.get(CHAVE_NOVIDADES)
    if secao is None:
        return "sem_registro", None
    if not isinstance(secao, dict):
        return "ilegivel", None
    valor = secao.get("ultima_versao_vista")
    if valor is None:
        return "sem_registro", None
    if not isinstance(valor, str) or not valor:
        return "ilegivel", None
    return "vista", valor


# =============================================================================
# Colunas lembradas de cada tabela  [2026-10-26]
# =============================================================================
# Ordem, largura e visibilidade das colunas de uma tabela da interface
# (`sigft/app_qt/widgets/colunas.py`), pela CHAVE da tabela. O valor é o que
# `colunas.descrever` monta (uma lista de dicts); validar é de quem lê
# (`colunas.juntar`), que trata valor estragado como "nunca gravado".
CHAVE_COLUNAS = "colunas"


def ler_colunas(
    chave: str,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> object:
    """O que foi guardado para a tabela `chave`, cru; `None` se nada."""
    return _carregar_estado(config_path).get(CHAVE_COLUNAS, {}).get(chave)


def gravar_colunas(
    chave: str,
    valor: object,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> None:
    """Guarda `valor` para a tabela `chave`; `None` apaga (o "Restaurar colunas")."""
    estado = _carregar_estado(config_path)
    secao = estado.setdefault(CHAVE_COLUNAS, {})
    if valor is None:
        secao.pop(chave, None)
    else:
        secao[chave] = valor
    _salvar_estado(estado, config_path)
